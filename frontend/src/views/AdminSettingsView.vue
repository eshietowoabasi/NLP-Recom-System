<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import ErrorAlert from '../components/ErrorAlert.vue'
import { api } from '../services/api'

// Spec v2 §1: system-wide NLP parameter defaults, managed by Administrators.
const config = reactive({})
const error = ref(null)
const saved = ref(false)
const weightSum = computed(() => +((config.ner_weight || 0) + (config.topic_weight || 0) + (config.novelty_weight || 0)).toFixed(4))
const fields = [
  { key: 'similarity_threshold', label: 'Overlap threshold (SBERT cosine)', step: 0.01, min: 0, max: 1, help: 'Candidates at or above this similarity to the NUC core are flagged.' },
  { key: 'ner_weight', label: 'NER demand weight', step: 0.05, min: 0, max: 1 },
  { key: 'topic_weight', label: 'BERTopic relevance weight', step: 0.05, min: 0, max: 1 },
  { key: 'novelty_weight', label: 'Novelty weight', step: 0.05, min: 0, max: 1 },
  { key: 'topic_count', label: 'Topic count (BERTopic)', step: 1, min: 2, max: 100 },
  { key: 'max_recommendations', label: 'Recommendations shown', step: 1, min: 1, max: 100 },
]

onMounted(async () => {
  try {
    Object.assign(config, (await api.get('/admin/settings/nlp-defaults')).parameter_config)
  } catch (e) {
    error.value = e
  }
})

async function save() {
  error.value = null
  saved.value = false
  try {
    Object.assign(config, (await api.put('/admin/settings/nlp-defaults', { ...config })).parameter_config)
    saved.value = true
  } catch (e) {
    error.value = e
  }
}
</script>

<template>
  <h1 class="h3 mb-1">NLP defaults</h1>
  <p class="text-body-secondary small">New analysis sessions start with these values; planners can still adjust them per session.</p>
  <ErrorAlert :error="error" />
  <div v-if="saved" class="alert alert-success py-2" data-test="settings-saved">Defaults saved.</div>
  <form class="card card-body" style="max-width: 40rem" data-test="settings-form" @submit.prevent="save">
    <div v-for="f in fields" :key="f.key" class="row g-2 align-items-center mb-2">
      <label class="col-sm-7 col-form-label small" :for="f.key">{{ f.label }}</label>
      <div class="col-sm-5">
        <input :id="f.key" v-model.number="config[f.key]" class="form-control form-control-sm" type="number" :step="f.step" :min="f.min" :max="f.max" required />
      </div>
      <div v-if="f.help" class="col-12 form-text mt-0">{{ f.help }}</div>
    </div>
    <div class="small mb-2" :class="weightSum === 1 ? 'text-body-secondary' : 'text-danger'">Weights sum to {{ weightSum }} (must be 1.0).</div>
    <div><button class="btn btn-primary" type="submit">Save defaults</button></div>
  </form>
</template>
