# Translation editing

You can fill translations yourself in these files:

- `locale/en/LC_MESSAGES/django.po` — English
- `locale/kk/LC_MESSAGES/django.po` — Kazakh

## How to edit

1. Open one of the `.po` files.
2. Find the needed `msgid`.
3. Fill or change the `msgstr` value.
4. Save the file.

## How to apply changes

Run this command from `c:\libraryy\libra`:

```powershell
c:/libraryy/venv/Scripts/python.exe manage.py compile_locales
```

Then restart the Django server or refresh the page.

> If you want a quick phrase list, see `locale/strings.txt`.
