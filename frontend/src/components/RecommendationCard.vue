<script setup>
import { ref } from 'vue'
import OverlapBadge from './OverlapBadge.vue'
import ScoreBreakdown from './ScoreBreakdown.vue'
import StatusBadge from './StatusBadge.vue'

// Spec v2 §8: title, composite score, accept/reject (single click, with undo),
// expandable evidence panel, score breakdown, overlap badge, planner notes.
const props = defineProps({
  rec: { type: Object, required: true },
  canReview: { type: Boolean, default: false },
  busy: { type: Boolean, default: false },
  weights: { type: Object, default: undefined },
  threshold: { type: Number, default: null },
})
const emit = defineEmits(['decide'])
const notes = ref(props.rec.planner_notes || '')
const showEvidence = ref(false)
const isFlagged = () => props.rec.overlap_status === 'Potential Duplicate'

function decide(decision) {
  emit('decide', { rec: props.rec, decision, notes: notes.value })
}
</script>

<template>
  <div class="card h-100" :data-test="`rec-${rec.rec_id}`">
    <div class="card-body d-flex flex-column">
      <div class="d-flex justify-content-between align-items-start gap-2 mb-2">
        <h2 class="h6 mb-0 min-w-0">
          <span class="text-body-secondary me-1">#{{ rec.rank }}</span>
          <RouterLink :to="`/recommendations/${rec.rec_id}`" data-test="rec-title">{{ rec.topic_title }}</RouterLink>
        </h2>
        <span class="fs-5 fw-semibold text-nowrap" title="Composite score">{{ rec.composite_score.toFixed(2) }}</span>
      </div>
      <div class="d-flex flex-wrap gap-1 mb-2">
        <OverlapBadge :status="rec.overlap_status" :similarity="rec.max_similarity" :threshold="threshold" />
        <StatusBadge :status="rec.planner_decision" data-test="decision-badge" />
      </div>
      <p class="small text-body-secondary mb-2">{{ rec.topic_description }}</p>
      <ScoreBreakdown
        :ner="rec.ner_score"
        :topic="rec.topic_score"
        :novelty="rec.novelty_score"
        :composite="rec.composite_score"
        :weights="weights"
        compact
      />
      <div v-if="rec.evidence?.passages?.length" class="mt-2">
        <button type="button" class="btn btn-link btn-sm px-0" :aria-expanded="showEvidence" data-test="toggle-evidence" @click="showEvidence = !showEvidence">
          {{ showEvidence ? 'Hide evidence' : `Show evidence (${rec.evidence.passages.length} passages)` }}
        </button>
        <div v-if="showEvidence" data-test="evidence-panel">
          <p v-for="(p, i) in rec.evidence.passages" :key="i" class="passage small mb-1">“{{ p.text }}”</p>
          <div v-if="rec.evidence.core_matches?.length" class="small text-body-secondary mt-1">
            Closest NUC core content: “{{ rec.evidence.core_matches[0].text }}”
          </div>
        </div>
      </div>
      <div v-if="canReview" class="mt-auto pt-3">
        <textarea
          v-model="notes"
          class="form-control form-control-sm mb-2"
          rows="2"
          :placeholder="isFlagged() ? 'Flagged: add a justification to accept' : 'Planner notes (optional)'"
          aria-label="Planner notes"
        ></textarea>
        <div v-if="!rec.planner_decision" class="btn-group btn-group-sm w-100" role="group" aria-label="Decision">
          <button class="btn btn-outline-success" :disabled="busy" data-test="accept" @click="decide('Accepted')">Accept</button>
          <button class="btn btn-outline-danger" :disabled="busy" data-test="reject" @click="decide('Rejected')">Reject</button>
        </div>
        <div v-else class="d-flex justify-content-between align-items-center small">
          <span>{{ rec.planner_decision }}</span>
          <button class="btn btn-link btn-sm p-0" :disabled="busy" data-test="undo" @click="decide(null)">Undo</button>
        </div>
      </div>
      <div v-else-if="rec.planner_notes" class="mt-auto pt-2 small"><strong>Notes:</strong> {{ rec.planner_notes }}</div>
    </div>
  </div>
</template>
