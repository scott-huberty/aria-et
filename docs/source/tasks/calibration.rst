.. _task-calibration:

Child-Friendly Calibration
==========================

.. vimeo:: 1214478085

`Child-friendly calibration video <https://vimeo.com/1214478085>`__

Description
-----------

The child-friendly calibration is run by `DeToX
<https://pypi.org/project/dvst-detox/>`__ (``dvst-detox``), a PsychoPy and Tobii
SDK toolkit for infant-friendly eye tracking. aria-et resolves the tracker,
opens the PsychoPy window on the configured stimulus display, and hands the
calibration to DeToX:

1. **Positioning.** A screen shows the child's eye positions inside the
   tracker's track box and their distance from the screen. Press Space when the
   child is well positioned. Skip it with ``--skip-positioning``.
2. **Calibration.** Animated cartoon targets, with an attention-getting sound,
   appear at 5 points (corners and center) or 9 points. The operator presses a
   number key to show a target and Space to collect when the child is looking at
   it.
3. **Results.** Enter computes the calibration and shows the collected gaze
   against each target. The operator can redo individual points, restart, or
   accept. Escape aborts without saving.
4. **Validation.** After the calibration is accepted, aria-et shows targets
   again at the same positions as the calibration (the four corners, 10% in
   from each edge, and the centre), in shuffled order, so accuracy is measured
   across the whole calibrated area. The operator presses Space when the child
   looks at each one; after the same settle DeToX uses before collecting
   (``focus_time``, 0.5 s, while the sound fades out), 1 s of gaze is
   recorded. Escape skips the rest of the validation and keeps the calibration.
5. **Results.** Like Titta, the stimulus screen then shows each target with
   the validation gaze of each eye (in DeToX's eye colours) and the quality
   table (accuracy, precision and data loss per eye, the same numbers as the
   GUI). Keys: **Space** accepts and saves; **V** re-runs the validation;
   **C** re-calibrates (positioning, DeToX, then validation again). If a
   re-calibration is aborted, the previous calibration is still active on the
   tracker, so its results are shown again. **Escape** also accepts: the
   calibration is already active on the tracker, so it is always recorded.

An accepted calibration is applied on the tracker and saved under the session's
``calibrations/`` folder (``calibration.bin`` and ``calibration.json``, method
``child-friendly-detox``). Later runs record it as the calibration in effect.

Calibration quality
-------------------

The validation step measures, for each eye (following Titta's method):

- **Accuracy (deg):** median angle between the gaze direction and the direction
  to the target, averaged over targets.
- **Precision (deg):** RMS of the angles between consecutive gaze samples
  (RMS-S2S), averaged over targets.
- **Data loss (%):** share of samples without valid gaze.

The results are saved in ``calibration.json`` (``validation``) and shown on the
GUI Calibration page as a table for the latest calibration, so the operator can
decide whether to recalibrate. The BIDS export writes ``AverageCalibrationError``
and ``MaximalCalibrationError`` (accuracy, in degrees) to each eye's
``*_physio.json``, along with ``CalibrationType``, ``CalibrationPosition`` and
``CalibrationCount``. ETM calibrations and skipped validations have no quality
numbers.

Study tolerance
~~~~~~~~~~~~~~~

A calibration is good enough when its validation **accuracy is at most 2.5°
in at least one eye**. This matches the ABCCT criterion ("calibration error
< 2.5°", ABCCT ET MOP v5.1 and Shic et al. 2022), which ABCCT also applied when
either eye met it. ABCCT checked it per trial during the tasks; aria-et checks
it at validation, right after calibrating, so it's a minimum bar: accuracy
tends to worsen during a session. Precision and data loss are shown for
information only.

The results screen shows the verdict under the quality table (green when
within tolerance, amber when not, with "re-calibrate before collecting data").
The GUI quality card shows the same line, as a warning banner when the
calibration is above tolerance, and each history entry ends with "within
tolerance" or "above tolerance". The verdict is also saved in
``calibration.json`` (``validation.tolerance``). The threshold is
``ACCURACY_TOLERANCE_DEG`` in ``aria_et/calibration.py``.

Options
-------

.. list-table::
   :header-rows: 1
   :widths: 30 50 20

   * - Option
     - Effect
     - Default
   * - ``--points {5,9}``
     - Number of calibration targets.
     - ``5``
   * - ``--no-shuffle``
     - Present targets in a fixed order.
     - shuffled
   * - ``--animation {zoom,trill}``
     - Target animation.
     - ``zoom``
   * - ``--no-sound``
     - Turn off the attention-getting sound.
     - sound on
   * - ``--skip-positioning``
     - Skip the positioning screen.
     - shown

``aria-et demo-calibration`` previews the same procedure without a tracker,
using the mouse in place of gaze. Nothing is saved.

Eye Tracker Manager calibration
-------------------------------

The GUI always runs the child-friendly calibration. If a session needs a
standard Tobii Pro Eye Tracker Manager calibration instead, run it from the
command line so aria-et records it:

.. code-block:: powershell

   aria-et calibrate-eyetracker --routine etm --subject <label> --session <label>

Don't calibrate in the Eye Tracker Manager application directly: the
calibration would be applied on the tracker but not recorded, so later runs
would record the previous aria-et calibration as the one in effect.
