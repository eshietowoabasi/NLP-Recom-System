<script setup>
import { ref } from 'vue'

// Tag input for course-code lists (spec v2 §8 CurriculumMapForm prerequisites).
const model = defineModel({ type: Array, default: () => [] })
const props = defineProps({ id: { type: String, default: undefined }, placeholder: { type: String, default: '' } })
const draft = ref('')

function add() {
  const values = draft.value.split(',').map((v) => v.trim()).filter(Boolean)
  const next = [...model.value]
  for (const v of values) if (!next.some((t) => t.toLowerCase() === v.toLowerCase())) next.push(v)
  model.value = next
  draft.value = ''
}

function remove(i) {
  model.value = model.value.filter((_, j) => j !== i)
}

function onKey(e) {
  if (e.key === 'Enter' || e.key === ',') {
    e.preventDefault()
    add()
  } else if (e.key === 'Backspace' && !draft.value && model.value.length) {
    remove(model.value.length - 1)
  }
}
</script>

<template>
  <div class="form-control d-flex flex-wrap gap-1 align-items-center" data-test="tag-input">
    <span v-for="(tag, i) in model" :key="tag" class="badge text-bg-light border d-inline-flex align-items-center gap-1">
      {{ tag }}
      <button type="button" class="btn-close" style="font-size: 0.55rem" :aria-label="`Remove ${tag}`" @click="remove(i)"></button>
    </span>
    <input
      :id="props.id"
      v-model="draft"
      class="border-0 flex-grow-1"
      style="outline: none; min-width: 8rem"
      :placeholder="model.length ? '' : props.placeholder"
      @keydown="onKey"
      @blur="add"
    />
  </div>
</template>
