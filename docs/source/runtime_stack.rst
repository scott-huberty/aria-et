.. _runtime-stack:

Runtime Stack
=============

The Python environment files document package-level dependencies, but production
acquisition also depends on operating-system services, Tobii runtime components,
display configuration, tracker firmware, and PsychoPy media backends.

This page records the currently validated runtime stack. The values below are
from the macOS development/lab machine used during implementation. When the
Windows production acquisition PC is configured and validated, this page should
be updated so all production PCs in the study can be matched against the same
canonical stack.

Observed Validated Stack
------------------------

.. list-table::
   :header-rows: 1
   :widths: 30 35 35

   * - Component
     - Observed version or value
     - Notes
   * - Operating system
     - macOS ``14.6.1`` build ``23G93``
     - Current development/lab machine.
   * - Platform
     - ``macOS-14.6.1-x86_64-i386-64bit``
     - Reported by Python ``platform.platform()``.
   * - Python
     - ``3.10.20``
     - From ``/Users/scotterik/miniforge3/envs/aria-et_310``.
   * - PsychoPy
     - ``2026.2.1``
     - Task display, timing, audio, and movie presentation.
   * - Tobii SDK Python package
     - ``tobii-research`` ``2.1.0``
     - Installed package version. The SDK reports ``2.1.0.1`` at runtime in tracker checks.
   * - Tobii Pro Network Runtime
     - ``2.14.1.0_b3c0e9b569``
     - Encoded in ``platform_runtime_TOBIIPRONETWORK_MAC_x64_service``.
   * - Tobii Pro Eye Tracker Manager
     - ``2.7.2`` / build ``2.7.2.2562``
     - Used for the standard ETM calibration routine.
   * - Tracker model
     - ``Tobii Pro Spectrum``
     - Observed through the Tobii SDK.
   * - Tracker serial
     - ``TPSP1-010214213025``
     - Observed through the Tobii SDK.
   * - Tracker firmware
     - ``2.6.2-orbicularis-0``
     - Observed through the Tobii SDK.
   * - Tracker address
     - ``tobii-prp://169.254.10.180``
     - Auto-IP address observed during validation; this can change across boots.
   * - Stimulus display
     - EIZO / ``EV2480`` observed in PsychoPy logs
     - Production runs target PsychoPy ``screen=1`` in fullscreen mode.
   * - FFmpeg
     - ``7.1.1``
     - Used for stimulus conversion and media inspection.
   * - FFprobe
     - ``7.1.1``
     - Used for media inspection.

Observed PsychoPy Media Stack
-----------------------------

These packages and tools are installed in the validated Python environment and
may be used by PsychoPy depending on the stimulus type, audio preferences, and
platform.

.. list-table::
   :header-rows: 1
   :widths: 30 30 40

   * - Component
     - Observed version
     - Role
   * - ``ffpyplayer``
     - ``4.5.3``
     - Movie decoding and, in some PsychoPy paths, movie audio playback.
   * - ``psychtoolbox``
     - ``3.0.22.2``
     - Low-latency audio backend used by PsychoPy when available/configured.
   * - ``pyglet``
     - ``1.5.27``
     - PsychoPy windowing/OpenGL dependency.
   * - ``sounddevice``
     - ``0.5.5``
     - Audio backend dependency.
   * - ``pygame``
     - Not installed
     - Not part of the currently validated stack.

Backend Discovery Limits
------------------------

PsychoPy can select different lower-level backends based on installed packages,
preferences, platform, and stimulus type. We can reliably document installed
package versions, command-line tool versions, PsychoPy preferences, and runtime
warnings written to ``session.log``. We should not assume that every dynamic
library or OS media API loaded by PsychoPy can be identified portably from a
static dependency list.

For production, treat the session log as part of the runtime record. It captures
important warnings about monitor fallback, speaker fallback, movie playback, and
audio backend selection.

How To Verify The Current Stack
-------------------------------

Useful checks on the acquisition machine include:

.. code-block:: bash

   sw_vers
   /Users/scotterik/miniforge3/envs/aria-et_310/bin/python -m aria_et.cli check-eyetracker
   /Users/scotterik/miniforge3/envs/aria-et_310/bin/python -c "import psychopy; print(psychopy.__version__)"
   /Users/scotterik/miniforge3/envs/aria-et_310/bin/ffmpeg -version
   /Users/scotterik/miniforge3/envs/aria-et_310/bin/ffprobe -version

TODO
----

Add ``aria-et sys-info`` to print and optionally save a runtime stack report.
The report should include Python, PsychoPy, Tobii SDK, Tobii Pro Network
Runtime, Tobii Pro Eye Tracker Manager, tracker model/serial/firmware, display
metadata, audio device, and available media backend/tool versions.
