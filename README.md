# TunnelCrab 🦀

A UX-first VLESS tunneling client for Windows with a living crab interface.

TunnelCrab is a desktop VLESS client built around one idea: a person who doesn't know
what Reality, SNI or a transport is should still be able to connect, understand what's
happening, and recover on their own when something breaks. The crab reacts to what's
going on, errors are explained in plain language, and the technical machinery stays out
of the way.

*[Русская версия ниже](#ru)*

## Download

TunnelCrab is distributed as a ready-to-use Windows installer through the official
**[GitHub Releases](https://github.com/theyhatelose/tunnelcrab/releases)**. Most users
should just download the latest installer there — you do not need the source code to run
the app.

This repository's source code is published for **transparency and review**. It is **not**
currently a full developer SDK or a reproducible build environment, and it intentionally
omits build, signing and packaging tooling.

## Supported

- VLESS + Reality over TCP
- VLESS + Reality over XHTTP / SplitHTTP
- HTTP(S) subscriptions (plaintext, base64, or mixed content)

## Not supported yet

- Hysteria2
- Shadowsocks
- Trojan
- VMess
- VLESS over TLS / WebSocket / gRPC import

Links for unsupported modes are recognized and politely refused with a plain-language
explanation, rather than failing silently.

## Requirements

- Windows 10 / 11
- Microsoft Edge WebView2 Runtime (preinstalled on most modern Windows)

## Platforms

TunnelCrab is currently focused on Windows 10 / 11.

Other platforms may be considered later if there is enough interest. If you would like to
see TunnelCrab on macOS, Linux, Android, or iOS, feel free to share feedback through
GitHub or the Telegram channel.

## Troubleshooting

- **Blank white window on Windows 10** usually means the Microsoft Edge WebView2 Runtime
  is missing. Install the Evergreen Runtime from
  https://developer.microsoft.com/microsoft-edge/webview2/ and restart TunnelCrab.
- **SmartScreen / "this app may harm your device"** is usually a reputation warning for
  early, unsigned or low-reputation builds — not a guaranteed malware verdict. Windows
  warns until a download builds up reputation. Choose "Keep" / "More info → Run anyway"
  if you trust the source.
- **Uninstalling** removes the app but keeps your data (profiles, settings, logs) under
  `%APPDATA%\TunnelCrab`, so reinstalling picks up where you left off. For a full cleanup,
  delete that folder manually. Logs live in `%APPDATA%\TunnelCrab\logs`.

## Release integrity

- Each installer on GitHub Releases is published together with a SHA256 checksum sidecar
  (`<installer>.exe.sha256`). The in-app updater verifies this checksum before installing
  and refuses to run a download that doesn't match.
- Download TunnelCrab **only** from the official
  [GitHub Releases](https://github.com/theyhatelose/tunnelcrab/releases) page.

## License

MIT — see [LICENSE](LICENSE).

---

<a id="ru"></a>

# TunnelCrab 🦀 — Русская версия

Удобный Windows-клиент для VLESS/Reality с живым крабиком в интерфейсе.

TunnelCrab сделан вокруг простой идеи: подключение не должно требовать от пользователя
разбираться в Reality, SNI, типах подключения и технических логах. Достаточно добавить
ссылку или подписку, выбрать сервер и нажать одну кнопку. Краб реагирует на происходящее,
а если что-то идёт не так — объясняет причину понятным языком.

## Загрузка

TunnelCrab распространяется как готовое приложение для Windows через официальные
**[GitHub Releases](https://github.com/theyhatelose/tunnelcrab/releases)**. Большинству
пользователей достаточно скачать оттуда последнюю версию — исходный код для запуска
приложения не нужен.

Исходный код в этом репозитории опубликован для **прозрачности и ревью**. Сейчас это
**не** полный developer SDK и не воспроизводимая сборочная среда; инструменты сборки,
подписи и упаковки сюда сознательно не входят.

## Поддерживается

- VLESS + Reality поверх TCP
- VLESS + Reality поверх XHTTP / SplitHTTP
- Подписки по HTTP(S) (обычный текст, base64 или смешанное содержимое)

## Пока не поддерживается

- Hysteria2
- Shadowsocks
- Trojan
- VMess
- Импорт VLESS поверх TLS / WebSocket / gRPC

Ссылки на неподдерживаемые режимы распознаются и вежливо отклоняются с понятным
объяснением, а не ломаются молча.

## Требования

- Windows 10 / 11
- Microsoft Edge WebView2 Runtime (предустановлен в большинстве современных Windows)

## Платформы

Сейчас TunnelCrab сфокусирован на Windows 10 / 11.

Другие платформы могут появиться позже, если будет достаточно интереса. Если тебе
хотелось бы увидеть TunnelCrab на macOS, Linux, Android или iOS — можно написать об этом
через GitHub или Telegram-канал.

## Устранение неполадок

- **Пустое белое окно на Windows 10** обычно значит, что не установлен Microsoft Edge
  WebView2 Runtime. Поставь Evergreen Runtime с
  https://developer.microsoft.com/microsoft-edge/webview2/ и перезапусти TunnelCrab.
- **SmartScreen / «приложение может навредить устройству»** — обычно это предупреждение о
  репутации для ранних, неподписанных или малоизвестных сборок, а не гарантированный
  вердикт о вирусе. Windows предупреждает, пока загрузка не накопит репутацию. Нажми
  «Сохранить» / «Подробнее → Выполнить в любом случае», если доверяешь источнику.
- **Удаление** убирает приложение, но сохраняет твои данные (профили, настройки, логи) в
  `%APPDATA%\TunnelCrab`, чтобы переустановка продолжила с того же места. Для полной
  очистки удали эту папку вручную. Логи лежат в `%APPDATA%\TunnelCrab\logs`.

## Целостность релиза

- Каждая сборка в GitHub Releases публикуется вместе с файлом контрольной суммы SHA256
  (`<имя-файла>.exe.sha256`). Встроенный апдейтер проверяет эту сумму перед установкой и
  отказывается запускать загрузку, которая не совпала.
- Скачивайте TunnelCrab **только** со страницы официальных
  [GitHub Releases](https://github.com/theyhatelose/tunnelcrab/releases).

## Лицензия

MIT — см. [LICENSE](LICENSE).
