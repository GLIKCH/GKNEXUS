# Frontend Customization

The Settings tab controls the GLIKCH NEXUZ visual layer without changing LM Studio or memory backend behavior.

## Stored Settings

Settings are saved in `MemoryManagement/docs/ui_settings.json` and include wallpapers, accent colors, neon strength, transparency, mascot visibility, and browser voice preferences.

## Voice Notes

Voice input and response playback use browser-native APIs when available. This keeps the project lightweight and avoids adding fragile packages. Speech recognition support depends on the browser.

## Mascot Notes

Mascot messages are private local presets stored through the emotion presets endpoint. Each line in the Settings text area becomes one possible mascot message.
