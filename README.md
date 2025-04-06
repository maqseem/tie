# 👔 Tie
Lightweight internationalization library for Python. 
## Features
- ✅ Intuitive YAML structure with wrapping, variable, and section support.
- 🌍 Built-in locale fallback and `$default_values`.
- 🧩 Dynamic string substitution with `{var}` and positional arguments.
- 📚 Tree rendering for export to a dictionary.

## Examples
### 1. tie.yaml:
```yaml
tie:
  version: 0.1.0
  default_locale: "en-US"

$greeting:
    ru-RU: "Привет"
    gr-GR: "Γεια"
    en-US: "Hello"
    fr-FR: "Bonjour"
    ja: "こんにちは!"

+subscription:
  $channel:
    en: "my"
    ru: "Essent Sight"
    gr-GR: "TedX Talks"
  request:
    wrap: "👋 {greeting}! {}!"
    ru-RU: "Подпишись на канал {channel}"
    gr-GR: "Εγγραφείτε στο κανάλι {channel}"
    en-US: "Subscribe to {channel} channel"
    fr-FR: "Veuillez vous abonner à la chaîne {channel}"
    ja: "{channel}チャンネルに登録してください"

  cancellation_confirmation:
    wrap: "{}?"
    en: "Are you sure you want to unsubscribe from {channel}"
    de: "Sind Sie sicher, dass Sie sich vom {channel}-Kanal abmelden möchten"
```
### 2. Python
```py
# Initializes a Tie instance with American English as the default locale
# and Greek as the main locale.
from tie import Tie
tie = Tie("tie.yaml", "en-US").set_locale("gr")

# Renders the Greek translation with the substitution of channel
print(tie.subscription.request(channel="Essent Sight"))
# -> 👋 Γεια! Εγγραφείτε στο κανάλι Essent Sight!

#  Renders the whole structure and saves it to JSON file.
import json
with open("rendered_tree", "w") as file:
    json.dump(tie.render_tree(channel="TedX Talks"), file)

#  Iterates and renders texts with randomized variables.
import random
for i, text in tie.set_locale("de").subscription:
  channel: str = random.choice(["The Primeagen", "Gleb Solomin", "The Weeknd"])
  print(f"{i}. {text(channel=channel)}")
  # -> 1. 👋 Hello! Subscribe to Gleb Solomin channel!
  # -> 2. Sind Sie sicher, dass Sie sich vom Gleb Solomin-Kanal abmelden möchten?
```

## Installation
Installation is pretty straightforward, it's `pip install tie`.

## Feedback
Feel free to open issues and suggest features!