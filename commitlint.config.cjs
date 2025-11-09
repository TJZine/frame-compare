// commitlint.config.cjs
/** @type {import('@commitlint/types').UserConfig} */
module.exports = {
  extends: ['@commitlint/config-conventional'],
  // Project-specific scopes for signal in releases & search
  rules: {
    'type-enum': [
      2, 'always',
      ['feat','fix','docs','chore','refactor','perf','test','ci','build','revert','style']
    ],
    'scope-enum': [
      2, 'always',
      [
        'hdr','sdr','vs','cli','report','html','analysis','audio',
        'tonemap','overlay','tmdb','geometry','color','ci','docs'
      ]
    ],
    'header-max-length': [2, 'always', 100],
    'subject-max-length': [2, 'always', 72],
    'subject-case': [2, 'never', ['sentence-case','start-case','pascal-case','upper-case']]
  },
  // Default ignores already cover "Merge", "Revert", "v1.2.3" etc.
  // Add bot patterns so CI doesn't fail on automated bumps.
  defaultIgnores: true,
  ignores: [
    (msg) => /^Bump\s.+\sto\s.+$/.test(msg),          // Dependabot style
    (msg) => /^chore\(deps\):/i.test(msg)             // Renovate style
  ],
  helpUrl: 'https://commitlint.js.org/'
};
