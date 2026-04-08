# Feature Ideas

Ideas collected during development — not yet implemented.

## Display & Content
- **Slideshow scheduling** — show different photo sources at different times of day (e.g. art during the day, family photos in the evening)
- **Clock mode** — full-screen clock face during configurable hours (e.g. bedside alarm clock)
- **Automatic strip text color** — detect average brightness of the underlying photo region and switch text to black or white automatically for better contrast
- **Per-photo EXIF strip** — show camera model, aperture, shutter speed from EXIF data alongside or instead of weather

## Info Strip
- **Calendar integration** — show next upcoming event from Google Calendar or CalDAV
- **Pollen forecast** — dedicated pollen API (e.g. Open-Meteo) for detailed allergen breakdown by type (grass, birch, olive...)
- **Indoor sensor data** — pull temperature/humidity from a local Home Assistant or MQTT sensor

## Hardware Integration
- **Physical GPIO button** — trigger next photo with a button wired to a Pi GPIO pin, no browser needed
- **NFC tag reader** — tap an NFC tag to trigger next photo (requires USB NFC reader)
- **Ambient light sensor** — skip the display refresh when the room is dark, reduce panel wear

## Remote & Automation
- **Email or Telegram alert** — notify when the service crashes or has not refreshed in 24h
- **Auto-update** — `git pull` on a nightly schedule and restart if code changed
- **Home Assistant integration** — expose a HA entity for display status; trigger next photo from HA automations
- **MQTT integration** — subscribe to an MQTT topic to trigger photo changes or push sensor readings into the strip

## Multi-Device
- **Multi-frame sync** — coordinate multiple frames on the same network to show different photos simultaneously via a shared SQLite or REST API

## Web UI
- **Web push notifications** — push a preview to the user's phone when a new photo is displayed
- **Dark/light mode toggle** — user preference stored in browser localStorage
- **Manual photo ordering** — drag to set which photo shows next
