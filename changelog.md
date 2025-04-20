Executing git changelog:
Initializing changelog options
loading changelog rc specification from .changelogrc
No changelog found [Error: ENOENT: no such file or directory, open '.changelogrc'] {
  errno: -2,
  code: 'ENOENT',
  syscall: 'open',
  path: '.changelogrc'
}
No .changelog.rc file found, using default settings
Sections:  Bug Fixes, Features, Documentation, Breaking changes, Refactor, Style, Test, Chore
  - The APP name is My app - Changelog
  - The output file is CHANGELOG.md
  - The template file is templates/template.md
  - The commit template file is templates/commit_template.md
Grep commits:  ^fix|^feat|^docs|BREAKING|^refactor|^style|^test|^chore
Getting last tag
Reading git log since the beggining
Executing :  git log  --grep="^fix|^feat|^docs|BREAKING|^refactor|^style|^test|^chore" -i -E --format=%H%n%s%n%b%n==END==
Parsed 1 commits
Generating changelog to CHANGELOG.md (  )
loading template from templates/template.md
loading commit template from  templates/commit_template.md
No custom template found [Error: ENOENT: no such file or directory, open 'templates/commit_template.md'] {
  errno: -2,
  code: 'ENOENT',
  syscall: 'open',
  path: 'templates/commit_template.md'
}
Found default template
Commit template loaded
No custom template found [Error: ENOENT: no such file or directory, open 'templates/template.md'] {
  errno: -2,
  code: 'ENOENT',
  syscall: 'open',
  path: 'templates/template.md'
}
Found default template
Finished generating log Yai!
