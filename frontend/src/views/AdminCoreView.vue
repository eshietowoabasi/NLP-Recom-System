<script setup>
import { onMounted, ref } from 'vue'
import DocumentUploader from '../components/DocumentUploader.vue'
import ErrorAlert from '../components/ErrorAlert.vue'
import StatusBadge from '../components/StatusBadge.vue'
import { api } from '../services/api'
import { dateTime } from '../utils/format'

// Spec v2 §8 AdminView: the NUC 70% core curriculum repository.
const CORE = 'NUC Core Reference'
const docs = ref([])
const error = ref(null)

async function load() {
  try {
    docs.value = (await api.get('/documents', { source_category: CORE, per_page: 100 })).items
  } catch (e) {
    error.value = e
  }
}

async function remove(doc) {
  if (!window.confirm(`Remove “${doc.title}” from the core curriculum? New analyses will no longer compare against it.`)) return
  try {
    await api.delete(`/documents/${doc.document_id}`)
    await load()
  } catch (e) {
    error.value = e
  }
}

onMounted(load)
</script>

<template>
  <h1 class="h3 mb-1">NUC core curriculum</h1>
  <p class="text-body-secondary small">
    Every analysis compares candidate topics with all parsed documents here to detect overlap with the NUC 70% core.
    A CSV course list (columns such as <code>course_code, course_title, description</code>) gives the most precise matches.
  </p>
  <div class="card card-body mb-3">
    <DocumentUploader :categories="[CORE]" :fixed-category="CORE" @uploaded="load" />
  </div>
  <ErrorAlert :error="error" />
  <div class="card">
    <div class="table-responsive">
      <table class="table table-sm mb-0" data-test="core-table">
        <thead><tr><th>Document</th><th>Type</th><th>Status</th><th>Words</th><th>Uploaded</th><th></th></tr></thead>
        <tbody>
          <tr v-for="d in docs" :key="d.document_id">
            <td>{{ d.title }}<div v-if="d.error_message" class="small text-danger">{{ d.error_message }}</div></td>
            <td class="small text-uppercase">{{ d.file_type }}</td>
            <td><StatusBadge :status="d.processing_status" /></td>
            <td class="small">{{ d.word_count ?? '–' }}</td>
            <td class="small">{{ dateTime(d.upload_timestamp) }}</td>
            <td class="text-end"><button class="btn btn-sm btn-link text-danger" @click="remove(d)">Remove</button></td>
          </tr>
          <tr v-if="!docs.length"><td colspan="6" class="small text-body-secondary p-3">No core curriculum uploaded yet; analyses cannot run until one is.</td></tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
