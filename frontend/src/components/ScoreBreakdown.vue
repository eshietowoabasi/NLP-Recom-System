<script setup>
import { computed, ref } from 'vue'
import { score } from '../utils/format'

// Spec v2 §8: visual breakdown of the three weighted components of S_c.
// Horizontal stacked bar (part-to-whole): each segment is weight x component score,
// so the bar length is the composite score on a 0-1 track. Categorical slots 1-3 of
// the validated palette; the legend below doubles as the table view and carries the
// numbers (the aqua slot is below 3:1 contrast, so visible labels are required).
const props = defineProps({
  ner: { type: Number, required: true },
  topic: { type: Number, required: true },
  novelty: { type: Number, required: true },
  composite: { type: Number, required: true },
  weights: { type: Object, default: () => ({ ner_weight: 0.4, topic_weight: 0.35, novelty_weight: 0.25 }) },
  compact: { type: Boolean, default: false },
})

const parts = computed(() => [
  { key: 'ner', label: 'NER skill demand', short: 'N', value: props.ner, weight: props.weights.ner_weight, color: 'var(--series-1)' },
  { key: 'topic', label: 'BERTopic relevance', short: 'B', value: props.topic, weight: props.weights.topic_weight, color: 'var(--series-2)' },
  { key: 'novelty', label: 'Novelty vs NUC core', short: 'V', value: props.novelty, weight: props.weights.novelty_weight, color: 'var(--series-3)' },
].map((p) => ({ ...p, contribution: (p.weight ?? 0) * (p.value ?? 0) })))

const visible = computed(() => parts.value.filter((p) => p.contribution > 0))
const hovered = ref(null)
const summary = computed(
  () => `Composite score ${score(props.composite)} = ` + parts.value.map((p) => `${score(p.weight)} × ${score(p.value)} (${p.label})`).join(' + '),
)
</script>

<template>
  <div class="score-breakdown" data-test="score-breakdown">
    <div class="d-flex justify-content-between align-items-baseline small mb-1">
      <span class="text-body-secondary">Score breakdown</span>
      <span class="fw-semibold">S = {{ score(composite) }}</span>
    </div>
    <div class="sb-track" role="img" :aria-label="summary" @mouseleave="hovered = null">
      <div
        v-for="(p, i) in visible"
        :key="p.key"
        class="sb-seg"
        :class="{ 'sb-end': i === visible.length - 1 }"
        :style="{ width: `${p.contribution * 100}%`, background: p.color }"
        :data-test="`segment-${p.key}`"
        @mouseenter="hovered = p"
        @focus="hovered = p"
        tabindex="0"
      ></div>
      <div v-if="hovered" class="sb-tip" role="tooltip">
        <strong>{{ hovered.label }}</strong><br />
        {{ score(hovered.weight) }} × {{ score(hovered.value) }} = {{ score(hovered.contribution, 3) }}
      </div>
    </div>
    <table v-if="!compact" class="sb-legend small mt-1">
      <tbody>
        <tr v-for="p in parts" :key="p.key">
          <td><span class="sb-swatch" :style="{ background: p.color }" aria-hidden="true"></span>{{ p.label }}</td>
          <td class="text-end text-body-secondary">{{ score(p.weight) }} × {{ score(p.value) }}</td>
          <td class="text-end fw-semibold">{{ score(p.contribution, 3) }}</td>
        </tr>
      </tbody>
    </table>
    <div v-else class="small text-body-secondary mt-1">
      <span v-for="p in parts" :key="p.key" class="me-2 text-nowrap">
        <span class="sb-swatch" :style="{ background: p.color }" aria-hidden="true"></span>{{ p.short }} {{ score(p.value) }}
      </span>
    </div>
  </div>
</template>

<style scoped>
.score-breakdown {
  --series-1: #2a78d6;
  --series-2: #eb6834;
  --series-3: #1baf7a;
  --track: #eef1f5;
  --surface: #ffffff;
}
.sb-track {
  position: relative;
  display: flex;
  gap: 2px; /* surface gap between stacked segments */
  height: 12px;
  background: var(--track);
  border-radius: 0 4px 4px 0;
}
.sb-seg {
  height: 100%;
  min-width: 2px;
  outline-offset: 2px;
}
.sb-end {
  border-radius: 0 4px 4px 0; /* rounded data end, baseline end square */
}
.sb-seg:hover,
.sb-seg:focus-visible {
  box-shadow: 0 0 0 2px var(--surface), 0 0 0 3px #52514e;
}
.sb-tip {
  position: absolute;
  bottom: calc(100% + 6px);
  left: 0;
  z-index: 5;
  background: #0b0b0b;
  color: #fff;
  font-size: 0.75rem;
  padding: 4px 8px;
  border-radius: 4px;
  white-space: nowrap;
  pointer-events: none;
}
.sb-legend {
  width: 100%;
}
.sb-legend td {
  padding: 1px 0;
}
.sb-swatch {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 2px;
  margin-right: 6px;
  vertical-align: -1px;
}
</style>
