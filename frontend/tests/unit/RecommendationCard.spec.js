import { mount, RouterLinkStub } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import RecommendationCard from '../../src/components/RecommendationCard.vue'

const rec = {
  rec_id: 5,
  rank: 1,
  topic_title: 'Cloud Computing and Kubernetes',
  topic_description: 'Theme found in 20 passages.',
  composite_score: 0.834,
  ner_score: 0.9,
  topic_score: 0.8,
  novelty_score: 0.7,
  max_similarity: 0.83,
  overlap_status: 'Potential Duplicate',
  planner_decision: null,
  planner_notes: null,
  evidence: { passages: [{ text: 'Deploy on Kubernetes.' }], core_matches: [{ text: 'CSC 305: Cloud basics' }] },
}

const factory = (props) =>
  mount(RecommendationCard, { props: { rec, threshold: 0.8, ...props }, global: { stubs: { RouterLink: RouterLinkStub } } })

describe('RecommendationCard', () => {
  it('shows score, overlap badge with similarity, breakdown and decision state', () => {
    const wrapper = factory()
    expect(wrapper.text()).toContain('Cloud Computing and Kubernetes')
    expect(wrapper.text()).toContain('0.83')
    const badge = wrapper.find('[data-test="overlap-badge"]')
    expect(badge.text()).toContain('Flagged')
    expect(badge.attributes('title')).toContain('0.83')
    expect(wrapper.find('[data-test="score-breakdown"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('Pending review')
  })

  it('keeps evidence collapsed until expanded', async () => {
    const wrapper = factory()
    expect(wrapper.find('[data-test="evidence-panel"]').exists()).toBe(false)
    await wrapper.find('[data-test="toggle-evidence"]').trigger('click')
    expect(wrapper.find('[data-test="evidence-panel"]').text()).toContain('Deploy on Kubernetes.')
  })

  it('hides decision controls from users who cannot review', () => {
    expect(factory({ canReview: false }).find('[data-test="accept"]').exists()).toBe(false)
  })

  it('offers single-click accept/reject only (no flag), with notes', async () => {
    const wrapper = factory({ canReview: true })
    expect(wrapper.find('[data-test="flag"]').exists()).toBe(false)
    expect(wrapper.find('textarea').attributes('placeholder')).toContain('justification')
    await wrapper.find('textarea').setValue('Applied practice beyond the core')
    await wrapper.find('[data-test="accept"]').trigger('click')
    expect(wrapper.emitted('decide')[0][0]).toMatchObject({ decision: 'Accepted', notes: 'Applied practice beyond the core' })
  })

  it('shows Undo after a decision, which resets it to pending', async () => {
    const wrapper = factory({ canReview: true, rec: { ...rec, planner_decision: 'Rejected' } })
    expect(wrapper.find('[data-test="accept"]').exists()).toBe(false)
    await wrapper.find('[data-test="undo"]').trigger('click')
    expect(wrapper.emitted('decide')[0][0]).toMatchObject({ decision: null })
  })
})
