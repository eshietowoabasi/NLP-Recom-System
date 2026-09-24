import { defineStore } from 'pinia'
import { api } from '../services/api'

// Spec v2 §1: Curriculum Planner and Administrator.
export const ROLES = { ADMIN: 'Admin', PLANNER: 'Curriculum Planner' }

export const useAuthStore = defineStore('auth', {
  state: () => ({ user: null, checked: false }),
  getters: {
    isAuthenticated: (s) => !!s.user,
    isAdmin: (s) => s.user?.role === ROLES.ADMIN,
    // Every role can upload, create and run sessions (spec v2 §1).
    canWrite: (s) => [ROLES.ADMIN, ROLES.PLANNER].includes(s.user?.role),
  },
  actions: {
    async fetchMe() {
      try {
        this.user = (await api.get('/auth/me')).user
      } catch {
        this.user = null
      } finally {
        this.checked = true
      }
      return this.user
    },
    async login(username, password) {
      this.user = (await api.post('/auth/login', { username, password })).user
      this.checked = true
    },
    async logout() {
      try {
        await api.post('/auth/logout')
      } finally {
        this.user = null
      }
    },
    /** Owner-or-Admin rule used by the API for decisions, mappings and runs. */
    canReview(session) {
      if (!this.user || !session) return false
      return this.isAdmin || (this.canWrite && session.user_id === this.user.user_id)
    },
  },
})
