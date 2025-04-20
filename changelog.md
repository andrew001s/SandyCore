# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/en/1.0.0/)
and this project adheres to [Semantic Versioning](http://semver.org/spec/v2.0.0.html).

<!-- insertion marker -->
## Unreleased

<small>[Compare with latest](https://github.com/andrew001s/SandyCore/compare/v1.0.0...HEAD)</small>

### Fixed

- fix: 🐛 corregir el comando de push en el flujo de trabajo de changelog para usar el token de acceso correcto ([934f087](https://github.com/andrew001s/SandyCore/commit/934f0875bd35680480bf2c45636c34683c06a2e3) by andrew001s).
- fix: 🐛 corregir comando de push en el flujo de trabajo de changelog para usar el token de acceso ([1b4c96e](https://github.com/andrew001s/SandyCore/commit/1b4c96e86c1d9a45245bbb5ccb9c3a8716dd67ea) by andrew001s).
- fix: 🐛 actualizar configuración de git para usar secretos en lugar de valores fijos ([fe6c246](https://github.com/andrew001s/SandyCore/commit/fe6c246f00d9264f91bd265b62f7dfd7597ae809) by andrew001s).
- fix: 🐛 agregar configuración de git antes de realizar el commit del changelog ([47e8be0](https://github.com/andrew001s/SandyCore/commit/47e8be091ea6b393a6145d34e0b2e9694dede5bd) by andrew001s).
- fix: 🐛 corregir salida del comando git changelog para generar el archivo changelog.md ([75df47f](https://github.com/andrew001s/SandyCore/commit/75df47fd7ecb0e27d8437ab4688a8d8f0bff4109) by andrew001s).
- fix: 🐛 corregir configuración del flujo de trabajo de changelog para usar Node.js en lugar de Python ([8b8e5c6](https://github.com/andrew001s/SandyCore/commit/8b8e5c6ae17baee1bc0928e0be89aac5ebc70d9a) by andrew001s).
- fix: 🐛 agregar manejo de excepciones en las funciones client_gemini y client_gemini_order ([96544b1](https://github.com/andrew001s/SandyCore/commit/96544b169582da99d166f9caf00430fbf39f6eb6) by andrew001s).
- fix: 🐛 manejar excepciones en las acciones del moderador ([da1796c](https://github.com/andrew001s/SandyCore/commit/da1796ccc34338aa5572af6f51ed4723d2cbe29d) by andrew001s).
- fix: 🐛 eliminar función check_keypress y su hilo asociado ([5825829](https://github.com/andrew001s/SandyCore/commit/582582956e9ed8efbd38842532ff76d0fa2a75cf) by andrew001s).

<!-- insertion marker -->
## [v1.0.0](https://github.com/andrew001s/SandyCore/releases/tag/v1.0.0) - 2025-04-09

<small>[Compare with v0.2.0-alpha](https://github.com/andrew001s/SandyCore/compare/v0.2.0-alpha...v1.0.0)</small>

### Fixed

- fix: :bug: eliminar archivo de licencia obsoleto ([f508576](https://github.com/andrew001s/SandyCore/commit/f508576a1fa86d74324227ab3612fa6a93f66d84) by andrew001s).

## [v0.2.0-alpha](https://github.com/andrew001s/SandyCore/releases/tag/v0.2.0-alpha) - 2025-04-06

<small>[Compare with v0.1.1-alpha](https://github.com/andrew001s/SandyCore/compare/v0.1.1-alpha...v0.2.0-alpha)</small>

### Fixed

- fix: :bug:  implementar bloqueo de hilo para la reproducción de audio ([1b6b059](https://github.com/andrew001s/SandyCore/commit/1b6b059ee68c0fb3c54cf0a2b61d6bc7271d080e) by andrew001s).

## [v0.1.1-alpha](https://github.com/andrew001s/SandyCore/releases/tag/v0.1.1-alpha) - 2025-03-28

<small>[Compare with first commit](https://github.com/andrew001s/SandyCore/compare/555b9c7d15ddfed6939327f86c7aa6b20fa730de...v0.1.1-alpha)</small>

### Fixed

- fix(personality): :bug: Corregir formato de respuestas en el archivo de personalidad y ajustar tamaño de chunk en el servicio de mensajes ([9e263c1](https://github.com/andrew001s/SandyCore/commit/9e263c172c8d740090918acc80f503e83f754669) by andrew001s).
- fix(personality): :bug: Corregir la descripción de la Vtuber Sandy en el archivo de personalidad ([4008c99](https://github.com/andrew001s/SandyCore/commit/4008c99f97baac5deab530b94b5fdd14c963eca7) by andrew001s).
- fix(messages): :bug: Activar la reproducción de audio en la función de manejo de mensajes ([3c587be](https://github.com/andrew001s/SandyCore/commit/3c587be6fd584292ab3f0dbc1d7dec6771e7aec4) by andrew001s).
- fix(gitignore): :bug: Fix .gitignore to ignore python venv and OS Files ([cae4759](https://github.com/andrew001s/SandyCore/commit/cae4759f341fdcb443e605e6d4ca787b48cb6f37) by andrew001s).

### Issue

- La opción de Conectar con Cuenta Bot no funciona por el momento.

