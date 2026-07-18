# Limitations

- OpenAI export formats may evolve.
- Non-text content types are preserved conservatively and may require additional adapters.
- Branch identifiers are deterministic within the normalized graph but are not platform-issued IDs.
- Restart-candidate logic is deliberately narrow and incomplete.
- Asset detection recognizes conservative `file-...` and `file_...` identifier forms only.
- The package does not determine whether an issued command was executed.
- The package does not perform live browser or network acquisition.
