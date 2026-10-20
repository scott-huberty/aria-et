System information and provenance
=================================

From the repository root, report the installed software with:

.. code-block:: powershell

   pixi run aria-et sys-info
   pixi run aria-et sys-info --json

The report includes Python, the active pixi/conda environment, the ARIA version
and editable checkout, configuration location and data root, core and media
packages, bundled native media versions, and installed Tobii software. Each
probe reports its own error without preventing the rest of the report.
The default command does not connect to a tracker or import PsychoPy/Qt.
Native media queries run in a subprocess with a four-second timeout to allow
cold starts. Git revision and status queries each have a two-second timeout
and report failures independently, so a failed status check preserves the
commit. A failed dirty-state check is reported as an error, not as a clean tree.

To explicitly query the saved tracker (with discovery by serial number as a
fallback), use:

.. code-block:: powershell

   pixi run aria-et sys-info --tracker

This adds the device name, model, serial, firmware, address, and runtime version
when available. Connection failures are informational and still exit with zero.

Archived snapshots
------------------

Every recording, including GUI and dry runs, saves ``sys_info.json`` alongside
``session.json``. Each calibration artifact directory also contains a snapshot.
Both metadata files reference it through ``sys_info_file``. Versions are stored
only in the snapshot, which has ``schema_version: 1`` and ``collected_at`` local
and UTC ISO timestamps. Archiving does not open another tracker connection.

Snapshot collection and writes are best effort: on failure an error snapshot
and a log entry are attempted, and acquisition continues. Snapshots remain in
sourcedata; BIDS export does not copy them.

Read an archived file or directory as the same readable table:

.. code-block:: powershell

   pixi run aria-et sys-info --from path/to/run
   pixi run aria-et sys-info --from path/to/calibration/sys_info.json --json

``--from`` cannot be combined with ``--tracker``; it reports the archived
environment without querying the current machine.
