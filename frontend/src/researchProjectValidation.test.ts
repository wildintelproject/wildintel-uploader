import { describe, expect, it } from 'vitest'
import { EMPTY_RESEARCH_PROJECT } from './types'
import type { ResearchProjectDraft } from './types'
import { shownProjectErrors, validateResearchProject } from './researchProjectValidation'

const VALID: ResearchProjectDraft = { ...EMPTY_RESEARCH_PROJECT, name: 'Doñana', acronym: 'DONA' }

describe('validateResearchProject', () => {
  it('accepts a name and an acronym, the rest being Trapper\'s defaults', () => {
    expect(validateResearchProject(VALID)).toEqual({})
  })

  it('requires a name and an acronym', () => {
    const errors = validateResearchProject(EMPTY_RESEARCH_PROJECT)
    expect(errors.name).toBe('Required')
    expect(errors.acronym).toBe('Required')
  })

  it('limits the name to 255 characters and the acronym to 3–10', () => {
    expect(validateResearchProject({ ...VALID, name: 'x'.repeat(256) }).name).toMatch(/255/)
    expect(validateResearchProject({ ...VALID, acronym: 'AB' }).acronym).toMatch(/between 3 and 10/)
    expect(validateResearchProject({ ...VALID, acronym: 'ABCDEFGHIJK' }).acronym).toMatch(/between 3 and 10/)
    expect(validateResearchProject({ ...VALID, acronym: 'ABC' })).toEqual({})
    expect(validateResearchProject({ ...VALID, acronym: 'ABCDEFGHIJ' })).toEqual({})
  })

  it('only lets the acronym hold what a folder name can', () => {
    for (const bad of ['a b c', '../evil', '.hidden', 'DÖNA', 'a/b/c']) {
      expect(validateResearchProject({ ...VALID, acronym: bad }).acronym, bad).toMatch(/Only letters, digits/)
    }
    expect(validateResearchProject({ ...VALID, acronym: 'DO_NA-1.0' })).toEqual({})
  })

  it('needs an event interval that is a whole number, 0 or more', () => {
    expect(validateResearchProject({ ...VALID, event_interval: null }).event_interval).toBe('Required')
    expect(validateResearchProject({ ...VALID, event_interval: -1 }).event_interval).toMatch(/0 or more/)
    expect(validateResearchProject({ ...VALID, event_interval: 1.5 }).event_interval).toMatch(/whole number/)
    expect(validateResearchProject({ ...VALID, event_interval: 30 })).toEqual({})
  })

  it('limits abstract, methods and description to 2000 characters', () => {
    const long = 'x'.repeat(2001)
    const errors = validateResearchProject({ ...VALID, abstract: long, methods: long, description: long })
    expect(errors.abstract).toMatch(/2000/)
    expect(errors.methods).toMatch(/2000/)
    expect(errors.description).toMatch(/2000/)
  })
})

describe('shownProjectErrors', () => {
  it('leaves out the fields that are only empty', () => {
    expect(shownProjectErrors(validateResearchProject(EMPTY_RESEARCH_PROJECT))).toEqual({
      name: undefined, acronym: undefined, event_interval: undefined, abstract: undefined, methods: undefined, description: undefined,
    })
  })
})
