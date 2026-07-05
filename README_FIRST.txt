BANJOFY 006.2.2 - LIBRARY WORKFLOW AND NOW/NEXT DIAGRAMS
=========================================================

Status
------
BUILD COMPLETE

Type
----
Complete release package.

Validation performed before release
-----------------------------------
- Parsed all Python files for syntax errors.
- Checked MainWindow for missing private self._method calls.
- Confirmed auto-save after analysis was removed.

Important behaviour change
--------------------------
Analysed songs are NO LONGER auto-saved to Library.
A song is saved only when the user clicks Save to Library.

Library workflow
----------------
- Library box is larger.
- Search results box is smaller.
- Clicking a Library item selects it and shows a status message.
- Send to Practice loads the selected Library item.
- Refresh Library reloads the Library list from disk.
- Go to Practice Studio only changes tab.

NOW/NEXT chord diagrams
-----------------------
- Grid remains chord names only.
- NOW and NEXT panels show simple banjo chord diagrams.
- Diagrams are placeholders and will be improved later.

Future note
-----------
A later build will move the Library into a clear portable folder near the app/user-chosen location.

GitHub Desktop instructions
---------------------------
1. Download and unzip this ZIP.
2. Copy ALL contents into your local Banjofy repository folder.
3. Allow Windows to replace files.
4. Open GitHub Desktop.
5. Commit summary: Banjofy 006.2.2 library workflow now next diagrams
6. Commit, then Push origin.
7. Wait for Actions, download and test.
