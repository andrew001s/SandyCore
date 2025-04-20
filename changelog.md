Executing git changelog:
Initializing changelog options
loading changelog rc specification from .changelogrc
Found changelog rc
  - The APP name is My app - Changelog
  - The output file is CHANGELOG.md
  - The template file is templates/template.md
  - The commit template file is templates/commit_template.md
Grep commits:  |||||||
Getting last tag
Reading git log since the beggining
Executing :  git log  --grep="|||||||" -i -E --format=%H%n%s%n%b%n==END==
Incorrect message: d2305c748aec7e167f6dad057648cfcae28a572d Merge remote-tracking branch 'refs/remotes/origin/main'
Parsed 1 commits
Generating changelog to CHANGELOG.md (  )
error TypeError: Cannot read property 'replace' of undefined
    at /opt/hostedtoolcache/node/14.21.3/x64/lib/node_modules/git-changelog/tasks/lib/organize-commits.js:70:40
    at Array.forEach (<anonymous>)
    at Changelog.organizeCommits (/opt/hostedtoolcache/node/14.21.3/x64/lib/node_modules/git-changelog/tasks/lib/organize-commits.js:69:19)
    at Changelog.writeChangelog (/opt/hostedtoolcache/node/14.21.3/x64/lib/node_modules/git-changelog/tasks/lib/write-change-log.js:26:23)
    at Changelog.generateFromCommits (/opt/hostedtoolcache/node/14.21.3/x64/lib/node_modules/git-changelog/tasks/lib/generate.js:10:15)
    at processTicksAndRejections (internal/process/task_queues.js:95:5)
Finished generating log Yai!
