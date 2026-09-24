<script setup>
import { computed, ref } from 'vue'
import { describeError, uploadWithProgress } from '../services/api'

// Spec v2 §8: drag-and-drop multi-file upload with type selector and progress bar.
const props = defineProps({
  categories: { type: Array, required: true },
  fixedCategory: { type: String, default: '' }, // e.g. "NUC Core Reference" on the admin page
})
const emit = defineEmits(['uploaded'])

const ACCEPT = '.pdf,.docx,.txt,.csv'
const MAX_BYTES = 20 * 1024 * 1024
const category = ref(props.fixedCategory || props.categories[0])
const items = ref([])
const dragging = ref(false)
const busy = computed(() => items.value.some((i) => i.state === 'uploading' || i.state === 'queued'))
const input = ref(null)

function add(fileList) {
  for (const file of Array.from(fileList || [])) {
    const ext = file.name.split('.').pop().toLowerCase()
    const item = { id: `${file.name}-${file.size}-${Math.random()}`, file, progress: 0, state: 'queued', message: '' }
    if (!['pdf', 'docx', 'txt', 'csv'].includes(ext)) Object.assign(item, { state: 'error', message: 'Unsupported type (PDF, DOCX, TXT or CSV)' })
    else if (file.size > MAX_BYTES) Object.assign(item, { state: 'error', message: 'Larger than 20 MB' })
    items.value.push(item)
  }
  if (input.value) input.value.value = ''
  run()
}

let running = false
async function run() {
  if (running) return
  running = true
  for (const item of items.value) {
    if (item.state !== 'queued') continue
    item.state = 'uploading'
    const form = new FormData()
    form.append('file', item.file)
    form.append('source_category', props.fixedCategory || category.value)
    try {
      const { document } = await uploadWithProgress('/documents', form, (p) => (item.progress = p))
      item.progress = 1
      if (document.processing_status === 'Parsed') {
        Object.assign(item, { state: 'done', message: `${document.word_count} words` })
      } else {
        Object.assign(item, { state: 'warning', message: document.error_message })
      }
      emit('uploaded', document)
    } catch (e) {
      Object.assign(item, { state: 'error', message: describeError(e) })
    }
  }
  running = false
}

function onDrop(e) {
  dragging.value = false
  add(e.dataTransfer?.files)
}

const clearFinished = () => (items.value = items.value.filter((i) => ['queued', 'uploading'].includes(i.state)))
const barClass = { uploading: '', done: 'bg-success', warning: 'bg-warning', error: 'bg-danger', queued: 'bg-secondary' }
const stateText = { queued: 'Waiting', uploading: 'Uploading', done: 'Uploaded', warning: 'Uploaded, text extraction failed', error: 'Not uploaded' }
</script>

<template>
  <div data-test="uploader">
    <div v-if="!fixedCategory" class="mb-2" style="max-width: 20rem">
      <label class="form-label small" for="upload-category">Source category for these files</label>
      <select id="upload-category" v-model="category" class="form-select form-select-sm">
        <option v-for="c in categories" :key="c">{{ c }}</option>
      </select>
    </div>
    <div
      class="drop-zone rounded text-center p-4"
      :class="{ dragging }"
      data-test="drop-zone"
      @dragover.prevent="dragging = true"
      @dragleave.prevent="dragging = false"
      @drop.prevent="onDrop"
    >
      <p class="mb-2">Drag and drop files here, or</p>
      <label class="btn btn-primary btn-sm mb-1" for="file-input">Choose files</label>
      <input id="file-input" ref="input" class="visually-hidden" type="file" multiple :accept="ACCEPT" aria-label="Choose files" @change="add($event.target.files)" />
      <div class="small text-body-secondary">PDF, DOCX, TXT or CSV · up to 20 MB each</div>
    </div>
    <ul v-if="items.length" class="list-unstyled mt-2 mb-0" data-test="upload-list">
      <li v-for="item in items" :key="item.id" class="small mb-2" :data-test="`upload-${item.state}`">
        <div class="d-flex justify-content-between gap-2">
          <span class="text-truncate">{{ item.file.name }}</span>
          <span class="text-nowrap" :class="{ 'text-danger': item.state === 'error', 'text-warning-emphasis': item.state === 'warning' }">
            {{ stateText[item.state] }}<template v-if="item.message"> · {{ item.message }}</template>
          </span>
        </div>
        <div class="progress" style="height: 4px" role="progressbar" :aria-valuenow="Math.round(item.progress * 100)" aria-valuemin="0" aria-valuemax="100" :aria-label="`${item.file.name} upload progress`">
          <div class="progress-bar" :class="barClass[item.state]" :style="{ width: `${(item.state === 'error' ? 1 : item.progress) * 100}%` }"></div>
        </div>
      </li>
    </ul>
    <button v-if="items.length && !busy" type="button" class="btn btn-link btn-sm px-0" @click="clearFinished">Clear list</button>
  </div>
</template>

<style scoped>
.drop-zone {
  border: 2px dashed #b8c4d4;
  background: #f8fafc;
  transition: background 0.15s;
}
.drop-zone.dragging {
  background: #e7f0fb;
  border-color: #2a78d6;
}
</style>
