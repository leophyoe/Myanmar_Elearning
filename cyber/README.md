# Cyber Range Content (`cyber/`)

Everything the cyber range serves lives in **one folder** — labs and CTF
challenges side by side:

```
cyber/
├── labs/          Lab bundles: Dockerfile, entrypoint, target app, README
│   └── <category>/<slug>/
├── challenges/    Challenge bundles: task text, fixtures, solver notes
│   └── <category>/<slug>/
└── README.md
```

`<category>` matches the choices on the models (`LabCategory`,
`ChallengeCategory`), `<slug>` is the record's slug. A lab's
`LabTemplate.docker_compose_path` stores the folder path relative to this
directory (e.g. `web/sqli_basics`).

## Why one folder

* The whole cyber range is one unit — a teacher uploading a lab and a teacher
  uploading a challenge drop into the same tree.
* Docker images will be **built from here** later: every `<slug>` folder is
  self-contained, so a build script can walk `cyber/labs/*/*/Dockerfile`.
* Teachers can upload a bundle from the studio
  (**Content Studio → Cyber Range**), which extracts it into the right place.

## Bundle layout

```
cyber/labs/web/sqli_basics/
├── Dockerfile        # image definition — built later
├── README.md         # what the lab teaches + how to run it
├── app.py            # target application (example)
└── setup.sh          # optional container bootstrap
```

Docker image building is **not wired up yet** — the folder is the contract it
will be built against. Nothing here is executed by the web app; bundles are
only stored and served as source material.

Uploads are size-limited and extension-checked (`CYBER_BUNDLE_MAX_MB`), and
path traversal outside this folder is rejected.
