import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import OverlapBadge from '../../src/components/OverlapBadge.vue'
import ScoreBreakdown from '../../src/components/ScoreBreakdown.vue'
import TagInput from '../../src/components/TagInput.vue'

describe('ScoreBreakdown', () => {
  // Spec v2 §6 worked example: 0.40(0.85) + 0.35(0.72) + 0.25(0.66) = 0.757.
  const props = { ner: 0.85, topic: 0.72, novelty: 0.66, composite: 0.757 }

  it('draws weighted contributions whose widths add up to the composite score', () => {
    const wrapper = mount(ScoreBreakdown, { props })
    const widths = ['ner', 'topic', 'novelty'].map((k) => parseFloat(wrapper.find(`[data-test="segment-${k}"]`).element.style.width))
    expect(widths[0]).toBeCloseTo(34, 5)
    expect(widths[1]).toBeCloseTo(25.2, 5)
    expect(widths[2]).toBeCloseTo(16.5, 5)
    expect(widths.reduce((a, b) => a + b)).toBeCloseTo(75.7, 5)
  })

  it('lists every component with its numbers (table view) and an accessible summary', () => {
    const wrapper = mount(ScoreBreakdown, { props })
    expect(wrapper.text()).toContain('0.40 × 0.85')
    expect(wrapper.text()).toContain('0.340')
    expect(wrapper.find('[role="img"]').attributes('aria-label')).toContain('Composite score 0.76')
  })

  it('uses session weights and shows a tooltip on hover', async () => {
    const wrapper = mount(ScoreBreakdown, { props: { ...props, weights: { ner_weight: 0.5, topic_weight: 0.25, novelty_weight: 0.25 } } })
    expect(parseFloat(wrapper.find('[data-test="segment-ner"]').element.style.width)).toBeCloseTo(42.5, 5)
    await wrapper.find('[data-test="segment-topic"]').trigger('mouseenter')
    expect(wrapper.find('[role="tooltip"]').text()).toContain('BERTopic relevance')
  })
})

describe('OverlapBadge', () => {
  it('shows Clear or Flagged with the similarity and the rule on hover', () => {
    const clear = mount(OverlapBadge, { props: { status: 'No Significant Overlap', similarity: 0.34, threshold: 0.8 } })
    expect(clear.text()).toContain('Clear')
    expect(clear.classes()).toContain('text-bg-success')
    const flagged = mount(OverlapBadge, { props: { status: 'Potential Duplicate', similarity: 0.86, threshold: 0.8 } })
    expect(flagged.text()).toContain('Flagged')
    expect(flagged.attributes('title')).toContain('≥ 0.80')
  })
})

describe('TagInput', () => {
  it('adds tags on Enter or comma, ignores duplicates and removes with the button', async () => {
    const wrapper = mount(TagInput, { props: { modelValue: [], 'onUpdate:modelValue': (v) => wrapper.setProps({ modelValue: v }) } })
    const input = wrapper.find('input')
    await input.setValue('CSC 201, csc 201')
    await input.trigger('keydown', { key: 'Enter' })
    expect(wrapper.props('modelValue')).toEqual(['CSC 201'])
    await input.setValue('CSC 301')
    await input.trigger('keydown', { key: ',' })
    expect(wrapper.props('modelValue')).toEqual(['CSC 201', 'CSC 301'])
    await wrapper.find('button[aria-label="Remove CSC 201"]').trigger('click')
    expect(wrapper.props('modelValue')).toEqual(['CSC 301'])
  })
})
