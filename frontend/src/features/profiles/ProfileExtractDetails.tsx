import {
  formatEnglishLevel,
  formatExperience,
  formatJobFamily,
  formatSeniority,
  groupSkillsByDepth,
  skillDepthLabels,
} from './format'
import type { ExtractedProfile } from './types'

interface ProfileExtractDetailsProps {
  profile: ExtractedProfile
}

const EMPTY = 'empty'

export function ProfileExtractDetails({ profile }: ProfileExtractDetailsProps) {
  const jobFamilies = profile.job_families ?? []
  const skillSegments = groupSkillsByDepth(profile.skills)

  return (
    <dl className="profile-extract-fields">
      <div className="profile-extract-row">
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
            {profile.seniority ? (
              formatSeniority(profile.seniority)
            ) : (
              <span className="profile-extract-empty">{EMPTY}</span>
            )}
          </dd>
        </div>

        <div>
          <dt>Experience</dt>
          <dd>
            {profile.experience == null ? (
              <span className="profile-extract-empty">{EMPTY}</span>
            ) : (
              formatExperience(profile.experience)
            )}
          </dd>
        </div>

        <div>
          <dt>English</dt>
          <dd>
            {profile.english_level == null ? (
              <span className="profile-extract-empty">{EMPTY}</span>
            ) : (
              formatEnglishLevel(profile.english_level)
            )}
          </dd>
        </div>
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

      <div>
        <dt>Resume</dt>
        <dd>
          {profile.text ? (
            <details className="profile-extract-spoiler">
              <summary>Show</summary>
              <pre className="profile-extract-text">{profile.text}</pre>
            </details>
          ) : (
            <span className="profile-extract-empty">{EMPTY}</span>
          )}
        </dd>
      </div>
    </dl>
  )
}
