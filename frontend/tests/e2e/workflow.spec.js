import { expect, test } from '@playwright/test'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

// Full workflow from the specification (v2 §10 system testing): login -> upload ->
// create session -> run -> review -> accept -> map -> report, plus admin pages.
// Needs users admin / planner / planner2 (password E2E_PASSWORD) and an empty database
// (tests/e2e/reset-db.sh).
const here = path.dirname(fileURLToPath(import.meta.url))
const fixture = (name) => path.join(here, 'fixtures', name)
const PASSWORD = process.env.E2E_PASSWORD || 'Passw0rd!'
const shots = process.env.E2E_SCREENSHOTS

async function login(page, username) {
  await page.goto('/login')
  await page.getByLabel('Username').fill(username)
  await page.getByLabel('Password').fill(PASSWORD)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page.getByTestId('current-user')).toContainText(username)
}

async function logout(page) {
  await page.getByRole('button', { name: 'Sign out' }).click()
  await expect(page).toHaveURL(/\/login/)
}

async function openAdmin(page, item) {
  await page.getByTestId('admin-menu').click()
  await page.getByRole('link', { name: item, exact: true }).click()
}

async function snap(page, name) {
  if (shots) await page.screenshot({ path: path.join(shots, `${name}.png`), fullPage: true })
}

test.describe.configure({ mode: 'serial' })

test('unauthenticated users are sent to login', async ({ page }) => {
  await page.goto('/sessions')
  await expect(page).toHaveURL(/\/login\?next=\/sessions$/)
  await page.getByLabel('Username').fill('planner')
  await page.getByLabel('Password').fill('wrong')
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page.getByRole('alert')).toContainText('Invalid username or password')
})

test('admin loads the NUC core curriculum and sets NLP defaults', async ({ page }) => {
  await login(page, 'admin')
  await expect(page.getByTestId('core-warning')).toBeVisible()
  await openAdmin(page, 'Core curriculum')
  await page.getByLabel('Choose files').setInputFiles(fixture('ccmas-core-sample.txt'))
  await expect(page.getByTestId('upload-done')).toHaveCount(1)
  await expect(page.getByTestId('core-table').locator('tbody tr')).toHaveCount(1)

  await openAdmin(page, 'NLP defaults')
  await expect(page.getByLabel('Topic count (BERTopic)')).toHaveValue('10')
  await page.getByLabel('Recommendations shown').fill('15')
  await page.getByRole('button', { name: 'Save defaults' }).click()
  await expect(page.getByTestId('settings-saved')).toBeVisible()
  await logout(page)
})

test('planner runs an analysis, reviews, maps and reports', async ({ page }) => {
  await login(page, 'planner')
  await page.getByRole('link', { name: 'Documents' }).click()
  // Planners cannot upload core references.
  await expect(page.getByLabel('Source category for these files').locator('option', { hasText: 'NUC Core Reference' })).toHaveCount(0)
  await page.getByLabel('Source category for these files').selectOption('Job Market Data')
  await page.getByLabel('Choose files').setInputFiles(['cloud', 'security', 'data'].map((t) => fixture(`${t}-job-adverts.txt`)))
  await expect(page.getByTestId('upload-done')).toHaveCount(3)
  await expect(page.getByTestId('documents-table').locator('tbody tr')).toHaveCount(4)
  await snap(page, '01-documents')

  await page.getByRole('link', { name: 'Sessions', exact: true }).click()
  await page.getByLabel('Session name').fill('E2E Computing Review')
  for (const theme of ['cloud', 'security', 'data']) await page.getByLabel(new RegExp(`^${theme}-job-adverts`)).check()
  await page.getByRole('button', { name: 'Show scoring parameters' }).click()
  await expect(page.getByLabel('Max recommendations')).toHaveValue('15') // Admin default applied
  await page.getByRole('button', { name: 'Create session' }).click()
  await expect(page).toHaveURL(/\/sessions\/\d+$/)
  await expect(page.getByTestId('session-status')).toHaveText('Pending')

  // Spec v2 §8: completion redirects straight to the recommendation dashboard.
  await page.getByTestId('run').click()
  await expect(page).toHaveURL(/\/sessions\/\d+\/recommendations$/, { timeout: 90_000 })
  const cards = page.locator('[data-test^="rec-"]').filter({ has: page.getByTestId('rec-title') })
  await expect(cards.first()).toBeVisible()
  expect(await cards.count()).toBeGreaterThan(2)
  await expect(cards.first().getByTestId('score-breakdown')).toBeVisible()
  await snap(page, '02-recommendations')

  // A flagged topic needs a justification; reject is one click and can be undone.
  const flagged = cards.filter({ has: page.getByTestId('overlap-badge').filter({ hasText: 'Flagged' }) }).first()
  await flagged.getByTestId('accept').click()
  await expect(page.getByRole('alert')).toContainText('requires planner notes')
  await flagged.getByTestId('reject').click()
  await expect(flagged.getByTestId('decision-badge')).toHaveText('Rejected')
  await flagged.getByTestId('undo').click()
  await expect(flagged.getByTestId('decision-badge')).toHaveText('Pending review')
  await flagged.getByTestId('reject').click()

  const clear = cards.filter({ has: page.getByTestId('overlap-badge').filter({ hasText: 'Clear' }) }).first()
  await clear.getByTestId('toggle-evidence').click()
  await expect(clear.getByTestId('evidence-panel')).toBeVisible()
  await clear.getByLabel('Planner notes').fill('Strong regional demand for cloud skills.')
  await clear.getByTestId('accept').click()
  await expect(clear.getByTestId('decision-badge')).toHaveText('Accepted')
  await expect(page.getByTestId('decision-counts')).toContainText('1 accepted · 1 rejected')

  await clear.getByTestId('rec-title').click()
  await expect(page.getByTestId('rec-heading')).toBeVisible()
  await snap(page, '03-recommendation-detail')
  // A slow mapping lookup must not wipe what the planner has already typed.
  await page.route('**/api/recommendations/*/mapping', async (route) => {
    if (route.request().method() === 'GET') await new Promise((resolve) => setTimeout(resolve, 1500))
    await route.continue()
  })
  const mappingLookup = page.waitForResponse((r) => r.url().endsWith('/mapping') && r.request().method() === 'GET')
  await page.getByTestId('map-link').click()
  await page.getByLabel('Course code').fill('uuy-csc411')
  await page.getByLabel('Course title').fill('Cloud-Native Application Development with Python')
  await page.getByLabel('Credit units').selectOption('3')
  await page.getByLabel('Prerequisites (press Enter after each code)').fill('CSC 201')
  await page.getByLabel('Prerequisites (press Enter after each code)').press('Enter')
  await page.getByLabel('Learning outcome 1').fill('Deploy containerised services on a public cloud')
  await mappingLookup
  await expect(page.getByLabel('Course code')).toHaveValue('uuy-csc411')
  await page.getByRole('button', { name: 'Save course' }).click()
  await expect(page.getByTestId('mapping-saved')).toHaveText('Saved UUY-CSC 411.')
  await snap(page, '04-mapping')

  await page.getByRole('link', { name: 'Sessions', exact: true }).click()
  await page.getByRole('link', { name: 'E2E Computing Review' }).click()
  await page.getByRole('link', { name: 'Evidence dashboard' }).click()
  await expect(page.getByText('Kubernetes').first()).toBeVisible()
  await page.getByTestId('tab-topics').click()
  await expect(page.getByText(/themes from \d+ passages/)).toBeVisible()
  await page.getByTestId('tab-similarity').click()
  await expect(page.getByTestId('overlap-badge').filter({ hasText: 'Flagged' }).first()).toBeVisible()
  await snap(page, '05-evidence-similarity')
  await page.getByRole('navigation').getByRole('link', { name: 'Session', exact: true }).click()

  const [download] = await Promise.all([page.waitForEvent('download'), page.getByTestId('report-pdf').click()])
  expect(download.suggestedFilename()).toMatch(/^NLP-RS_E2E_Computing_Review_.*\.pdf$/)
  await page.getByRole('link', { name: 'Reports' }).click()
  await expect(page.getByTestId('reports-table').locator('tbody tr')).toHaveCount(1)
  await logout(page)
})

test("another planner can read but not review someone else's session", async ({ page }) => {
  await login(page, 'planner2')
  await page.getByRole('link', { name: 'Sessions', exact: true }).click()
  await page.getByRole('link', { name: 'E2E Computing Review' }).click()
  await page.getByTestId('view-recommendations').click()
  await expect(page.getByTestId('score-breakdown').first()).toBeVisible()
  await expect(page.getByTestId('accept')).toHaveCount(0)
  await expect(page.getByTestId('admin-menu')).toHaveCount(0)
  await page.goto('/admin/users')
  await expect(page).toHaveURL(/\/dashboard/)
  await logout(page)
})

test('admin manages users and reviews the audit log', async ({ page }) => {
  await login(page, 'admin')
  await openAdmin(page, 'Users')
  await page.getByLabel('Username').fill('newplanner')
  await page.getByLabel('Email').fill('newplanner@uniuyo.edu.ng')
  await page.getByLabel('Password').fill('Another-pass1')
  await expect(page.getByLabel('Role', { exact: true }).locator('option')).toHaveText(['Admin', 'Curriculum Planner'])
  await page.getByRole('button', { name: 'Add user' }).click()
  await expect(page.getByText('Created newplanner.')).toBeVisible()
  await openAdmin(page, 'Audit log')
  for (const action of ['RECOMMENDATION_DECISION', 'MAPPING_CREATE', 'SETTINGS_UPDATE']) {
    await expect(page.getByText(action).first()).toBeVisible()
  }
  await snap(page, '06-audit-log')
})
