<script setup>
import { onMounted, reactive, ref } from 'vue'
import ErrorAlert from '../components/ErrorAlert.vue'
import TagInput from '../components/TagInput.vue'
import { api } from '../services/api'

// Spec v2 §8 CurriculumMapForm: one course per accepted recommendation (§4: 1-1).
const props = defineProps({ id: { type: String, required: true } })
const rec = ref(null)
const mapping = ref(null)
const error = ref(null)
const saved = ref('')
const form = reactive({ course_code: '', course_title: '', credit_units: 3, prerequisites: [], learning_outcomes: [''] })

function fill(m, title = rec.value?.topic_title) {
  Object.assign(form, m
    ? { course_code: m.course_code, course_title: m.course_title, credit_units: m.credit_units,
        prerequisites: [...m.prerequisites], learning_outcomes: m.learning_outcomes.length ? [...m.learning_outcomes] : [''] }
    : { course_code: '', course_title: title || '', credit_units: 3, prerequisites: [], learning_outcomes: [''] })
}

async function load() {
  try {
    const [recResult, mapResult] = await Promise.all([
      api.get(`/recommendations/${props.id}`),
      api.get(`/recommendations/${props.id}/mapping`),
    ])
    // Fill the form before it is shown (v-if="rec"), so nothing typed can be overwritten.
    mapping.value = mapResult.items[0] || null
    fill(mapping.value, recResult.recommendation.topic_title)
    rec.value = recResult.recommendation
  } catch (e) {
    error.value = e
  }
}

async function save() {
  error.value = null
  saved.value = ''
  const body = {
    course_code: form.course_code,
    course_title: form.course_title,
    credit_units: Number(form.credit_units),
    prerequisites: form.prerequisites,
    learning_outcomes: form.learning_outcomes.map((o) => o.trim()).filter(Boolean),
  }
  try {
    const result = mapping.value
      ? await api.put(`/mappings/${mapping.value.map_id}`, body)
      : await api.post(`/recommendations/${props.id}/mapping`, body)
    mapping.value = result.mapping
    fill(mapping.value)
    saved.value = `Saved ${result.mapping.course_code}.`
  } catch (e) {
    error.value = e
  }
}

async function remove() {
  if (!window.confirm(`Remove the mapping to ${mapping.value.course_code}?`)) return
  try {
    await api.delete(`/mappings/${mapping.value.map_id}`)
    mapping.value = null
    fill(null)
    saved.value = ''
  } catch (e) {
    error.value = e
  }
}

onMounted(load)
</script>

<template>
  <template v-if="rec">
    <nav class="small mb-2"><RouterLink :to="`/recommendations/${id}`">{{ rec.topic_title }}</RouterLink> / Curriculum mapping</nav>
    <h1 class="h3 mb-3">Curriculum mapping</h1>
  </template>
  <ErrorAlert :error="error" />
  <template v-if="rec">
  <div v-if="saved" class="alert alert-success py-2" data-test="mapping-saved">{{ saved }}</div>
  <form class="card card-body" style="max-width: 48rem" data-test="mapping-form" @submit.prevent="save">
    <h2 class="h6">{{ mapping ? `Edit ${mapping.course_code}` : 'Propose a course for this recommendation' }}</h2>
    <div class="row g-2">
      <div class="col-sm-4">
        <label class="form-label small" for="code">Course code</label>
        <input id="code" v-model="form.course_code" class="form-control" placeholder="UUY-CSC 411" required />
      </div>
      <div class="col-sm-8">
        <label class="form-label small" for="ctitle">Course title</label>
        <input id="ctitle" v-model="form.course_title" class="form-control" maxlength="255" required />
      </div>
      <div class="col-sm-4">
        <label class="form-label small" for="units">Credit units</label>
        <select id="units" v-model.number="form.credit_units" class="form-select">
          <option :value="1">1</option><option :value="2">2</option><option :value="3">3</option>
        </select>
      </div>
      <div class="col-sm-8">
        <label class="form-label small" for="prereq">Prerequisites (press Enter after each code)</label>
        <TagInput id="prereq" v-model="form.prerequisites" placeholder="CSC 201" />
      </div>
    </div>
    <label class="form-label small mt-3">Learning outcomes</label>
    <div v-for="(o, i) in form.learning_outcomes" :key="i" class="input-group input-group-sm mb-1">
      <span class="input-group-text">{{ i + 1 }}</span>
      <input v-model="form.learning_outcomes[i]" class="form-control" :aria-label="`Learning outcome ${i + 1}`" placeholder="Students will be able to…" />
      <button v-if="form.learning_outcomes.length > 1" type="button" class="btn btn-outline-secondary" @click="form.learning_outcomes.splice(i, 1)">Remove</button>
    </div>
    <button type="button" class="btn btn-link btn-sm px-0 align-self-start" @click="form.learning_outcomes.push('')">Add outcome</button>
    <div class="d-flex gap-2 mt-2">
      <button class="btn btn-primary" type="submit">{{ mapping ? 'Save changes' : 'Save course' }}</button>
      <button v-if="mapping" type="button" class="btn btn-outline-danger" @click="remove">Remove mapping</button>
    </div>
  </form>
  </template>
</template>
