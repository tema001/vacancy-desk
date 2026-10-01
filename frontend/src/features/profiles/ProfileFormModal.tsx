import { useRef, useState, type FormEvent } from 'react'
import {
  createProfile,
  isAbortError,
  isExtractedProfile,
  waitForProfileExtract,
} from './api'
import type { ExtractedProfile, ProfileSkill, SkillDepth } from './types'

interface ProfileFormModalProps {
  onClose: () => void
}

type ModalView = 'form' | 'loading' | 'result' | 'failed' | 'error'

const EMPTY = 'empty'

const englishLevelLabels: Record<number, string> = {
  1: 'A1',
  2: 'A2',
  3: 'B1',
  4: 'B2',
  5: 'C1',
  6: 'C2',
}

const jobFamilyLabels: Record<string, string> = {
  backend: 'Backend',
  frontend: 'Frontend',
  mobile: 'Mobile',
  data: 'Data',
  qa: 'QA',
  devops: 'DevOps',
  security: 'Security',
  embedded: 'Embedded',
  product: 'Product',
  delivery: 'Delivery',
  design: 'Design',
  support: 'Support',
  other: 'Other',
}

const skillDepthOrder: SkillDepth[] = [4, 3, 2, 1]

const skillDepthLabels: Record<SkillDepth, string> = {
  4: 'Expert',
  3: 'Advanced',
  2: 'Working',
  1: 'Familiarity',
}

function formatJobFamily(value: string): string {
  return jobFamilyLabels[value] ?? value
}

function formatSeniority(value: string): string {
  return value.charAt(0).toUpperCase() + value.slice(1)
}

function formatExperience(months: number): string {
  const years = Math.floor(months / 12)
  const yearLabel = years === 1 ? 'year' : 'years'
  const monthLabel = months === 1 ? 'month' : 'months'

  return `${years} ${yearLabel} (${months} ${monthLabel})`
}

function formatEnglishLevel(level: number): string {
  return englishLevelLabels[level] ?? String(level)
}

function groupSkillsByDepth(skills: ProfileSkill[]): {
  depth: SkillDepth
  skills: ProfileSkill[]
}[] {
  return skillDepthOrder
    .map((depth) => ({
      depth,
      skills: skills.filter((skill) => skill.depth === depth),
    }))
    .filter((segment) => segment.skills.length > 0)
}

export function ProfileFormModal({ onClose }: ProfileFormModalProps) {
  const [name, setName] = useState('')
  const [resumeText, setResumeText] = useState('')
  const [view, setView] = useState<ModalView>('form')
  const [extracted, setExtracted] = useState<ExtractedProfile | null>(null)
  const [errorMessage, setErrorMessage] = useState('')
  const abortRef = useRef<AbortController | null>(null)
  const canSubmit = resumeText.trim().length >= 10

  function showDialog(dialog: HTMLDialogElement | null): void {
    if (dialog && !dialog.open) {
      dialog.showModal()
    }
  }

  function handleClose(): void {
    abortRef.current?.abort()
    onClose()
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault()

    if (!canSubmit) {
      return
    }

    const trimmedName = name.trim()
    const controller = new AbortController()
    abortRef.current = controller
    setView('loading')
    setErrorMessage('')

    try {
      const created = await createProfile(
        {
          text: resumeText.trim(),
          name: trimmedName.length >= 5 ? trimmedName : null,
        },
        controller.signal,
      )
      const profile = await waitForProfileExtract(created.id, controller.signal)

      if (isExtractedProfile(profile)) {
        setExtracted(profile)
        setView('result')
        return
      }

      setView('failed')
    } catch (error) {
      if (isAbortError(error) || controller.signal.aborted) {
        return
      }

      setErrorMessage(
        error instanceof Error ? error.message : 'Could not extract profile',
      )
      setView('error')
    }
  }

  const jobFamilies = extracted?.job_families ?? []
  const skillSegments = extracted ? groupSkillsByDepth(extracted.skills) : []

  return (
    <dialog
      ref={showDialog}
      className="profile-modal"
      aria-labelledby="profile-modal-title"
      onCancel={handleClose}
    >
      <div className="profile-modal-heading">
        <h2 id="profile-modal-title">
          {view === 'result' && extracted ? extracted.name : 'Add a new profile'}
        </h2>
        <button
          type="button"
          className="profile-modal-close"
          onClick={handleClose}
          aria-label="Close add profile dialog"
        >
          ×
        </button>
      </div>

      {view === 'loading' ? (
        <div className="profile-extract-status" role="status">
          <span className="spinner large-spinner" aria-hidden="true" />
          <strong>Extracting profile</strong>
          <span>This usually takes a few seconds.</span>
        </div>
      ) : null}

      {view === 'failed' ? (
        <div className="profile-extract-status error-state" role="alert">
          <strong>Extract failed</strong>
          <span>The resume could not be processed. Try again with a different text.</span>
          <button type="button" className="primary-button" onClick={handleClose}>
            Close
          </button>
        </div>
      ) : null}

      {view === 'error' ? (
        <div className="profile-extract-status error-state" role="alert">
          <strong>Could not extract profile</strong>
          <span>{errorMessage}</span>
          <button type="button" className="primary-button" onClick={handleClose}>
            Close
          </button>
        </div>
      ) : null}

      {view === 'result' && extracted ? (
        <div className="profile-extract">
          <dl className="profile-extract-fields">
            <div>
              <dt>Job families</dt>
              <dd>
                {jobFamilies.length > 0 ? (
                  <ul className="profile-extract-tags">
                    {jobFamilies.map((family) => (
                      <li className="category-tag" key={family}>
                        {formatJobFamily(family)}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <span className="profile-extract-empty">{EMPTY}</span>
                )}
              </dd>
            </div>

            <div>
              <dt>Seniority</dt>
              <dd>
                {extracted.seniority ? (
                  formatSeniority(extracted.seniority)
                ) : (
                  <span className="profile-extract-empty">{EMPTY}</span>
                )}
              </dd>
            </div>

            <div>
              <dt>Experience</dt>
              <dd>
                {extracted.experience == null ? (
                  <span className="profile-extract-empty">{EMPTY}</span>
                ) : (
                  formatExperience(extracted.experience)
                )}
              </dd>
            </div>

            <div>
              <dt>English</dt>
              <dd>
                {extracted.english_level == null ? (
                  <span className="profile-extract-empty">{EMPTY}</span>
                ) : (
                  formatEnglishLevel(extracted.english_level)
                )}
              </dd>
            </div>

            <div>
              <dt>Skills</dt>
              <dd>
                {skillSegments.length > 0 ? (
                  <div className="profile-skill-segments">
                    {skillSegments.map((segment) => (
                      <section
                        className={`profile-skill-segment profile-skill-depth-${segment.depth}`}
                        key={segment.depth}
                      >
                        <h3>{skillDepthLabels[segment.depth]}</h3>
                        <ul className="profile-extract-tags">
                          {segment.skills.map((skill) => (
                            <li
                              className={`category-tag profile-skill-tag-${segment.depth}`}
                              key={skill.skill_name}
                            >
                              {skill.skill_name}
                            </li>
                          ))}
                        </ul>
                      </section>
                    ))}
                  </div>
                ) : (
                  <span className="profile-extract-empty">{EMPTY}</span>
                )}
              </dd>
            </div>
          </dl>

          <div className="profile-form-actions">
            <button type="button" className="primary-button" onClick={handleClose}>
              Done
            </button>
          </div>
        </div>
      ) : null}

      {view === 'form' ? (
        <form className="profile-form" onSubmit={(event) => void handleSubmit(event)}>
          <label>
            <span>
              Profile name <small>Optional</small>
            </span>
            <input
              type="text"
              value={name}
              autoFocus
              maxLength={100}
              placeholder="e.g. Senior Python Engineer"
              onChange={(event) => setName(event.target.value)}
            />
          </label>

          <label className="profile-resume-field">
            <span>Resume text</span>
            <textarea
              value={resumeText}
              required
              minLength={10}
              maxLength={5000}
              placeholder="Paste the full resume text here…"
              onChange={(event) => setResumeText(event.target.value)}
            />
          </label>

          <div className="profile-form-actions">
            <button
              type="button"
              className="secondary-button"
              onClick={handleClose}
            >
              Cancel
            </button>
            <button type="submit" className="primary-button" disabled={!canSubmit}>
              Upload
            </button>
          </div>
        </form>
      ) : null}
    </dialog>
  )
}
