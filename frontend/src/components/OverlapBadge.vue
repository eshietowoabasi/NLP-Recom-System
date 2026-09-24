<script setup>
import { computed } from 'vue'
import { score } from '../utils/format'

// Spec v2 §8: green "Clear" / amber "Flagged" badge with the similarity on hover.
// Status colours always come with an icon and a label, never colour alone.
const props = defineProps({
  status: { type: String, required: true }, // 'Potential Duplicate' | 'No Significant Overlap'
  similarity: { type: Number, default: null },
  threshold: { type: Number, default: null },
})
const flagged = computed(() => props.status === 'Potential Duplicate')
const detail = computed(() => {
  const sim = props.similarity == null ? '' : `Max similarity to the NUC 70% core: ${score(props.similarity)}`
  const rule = props.threshold == null ? '' : ` (flagged at ≥ ${score(props.threshold)})`
  return `${flagged.value ? 'Flagged: may duplicate the NUC core' : 'Clear: no significant overlap'}. ${sim}${rule}`.trim()
})
</script>

<template>
  <span
    class="badge"
    :class="flagged ? 'text-bg-warning' : 'text-bg-success'"
    :title="detail"
    :aria-label="detail"
    data-test="overlap-badge"
  >
    <span aria-hidden="true">{{ flagged ? '⚠' : '✓' }}</span>
    {{ flagged ? 'Flagged' : 'Clear' }}<template v-if="similarity != null"> · {{ score(similarity) }}</template>
  </span>
</template>
