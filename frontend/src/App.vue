<script setup>
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from './stores/auth'

const auth = useAuthStore()
const router = useRouter()
const menuOpen = ref(false)
const links = [
  { to: '/dashboard', label: 'Dashboard' },
  { to: '/documents', label: 'Documents' },
  { to: '/sessions', label: 'Sessions' },
  { to: '/reports', label: 'Reports' },
]
// Spec v2 §8 AdminView: users, core curriculum repository, NLP defaults, audit log.
const adminLinks = [
  { to: '/admin/users', label: 'Users' },
  { to: '/admin/core-curriculum', label: 'Core curriculum' },
  { to: '/admin/settings', label: 'NLP defaults' },
  { to: '/admin/audit', label: 'Audit log' },
]
const adminOpen = ref(false)
const route = useRoute()
const onAdminPage = computed(() => route.path.startsWith('/admin'))

async function logout() {
  await auth.logout()
  router.push({ name: 'login' })
}
</script>

<template>
  <nav v-if="auth.isAuthenticated" class="navbar navbar-expand-lg navbar-dark bg-rs mb-4">
    <div class="container-xl">
      <RouterLink class="navbar-brand" to="/dashboard">NLP-RS <small class="d-none d-xxl-inline">Curriculum Recommendation</small></RouterLink>
      <button class="navbar-toggler" type="button" aria-label="Toggle navigation" @click="menuOpen = !menuOpen">
        <span class="navbar-toggler-icon"></span>
      </button>
      <div class="collapse navbar-collapse" :class="{ show: menuOpen }">
        <ul class="navbar-nav me-auto">
          <li v-for="link in links" :key="link.to" class="nav-item">
            <RouterLink class="nav-link text-nowrap" active-class="active" :to="link.to" @click="menuOpen = false">{{ link.label }}</RouterLink>
          </li>
          <li v-if="auth.isAdmin" class="nav-item dropdown" @mouseleave="adminOpen = false">
            <button
              class="nav-link dropdown-toggle text-nowrap btn btn-link"
              :class="{ active: onAdminPage }"
              type="button"
              :aria-expanded="adminOpen"
              data-test="admin-menu"
              @click="adminOpen = !adminOpen"
            >
              Admin
            </button>
            <ul class="dropdown-menu" :class="{ show: adminOpen }">
              <li v-for="link in adminLinks" :key="link.to">
                <RouterLink class="dropdown-item" :to="link.to" @click="adminOpen = false; menuOpen = false">{{ link.label }}</RouterLink>
              </li>
            </ul>
          </li>
        </ul>
        <span class="navbar-text me-3 small text-nowrap" data-test="current-user">
          {{ auth.user.username }} · {{ auth.user.role }}
        </span>
        <button class="btn btn-outline-light btn-sm text-nowrap" type="button" @click="logout">Sign out</button>
      </div>
    </div>
  </nav>
  <main class="container-xl pb-5">
    <RouterView />
  </main>
</template>
