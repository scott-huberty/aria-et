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
   the validation gaze of each eye (in DeToX's eye colours), the quality
   table and the tolerance verdict (see *Calibration quality*; the same as the
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

Each metric is reported per eye as the **mean** over targets and the **worst**
single target. The results are saved in ``calibration.json`` (``validation``)
and shown as the same table on the stimulus screen after validation and on the
GUI Calibration page:

.. code-block:: text

                         Left eye          Right eye
                       Mean   Worst      Mean   Worst
   Accuracy (deg)      0.76   5.30 ✖     0.94   2.40 ✔
   Precision (deg)     0.07   0.11       0.06   0.10
   Data loss (%)       0      0          2      8

                   Within 2.5° tolerance: OK to proceed

The ✔ / ✖ next to each eye's worst accuracy marks whether that eye is within
the study tolerance (below). Marks are used rather than colour, so pass/fail
doesn't clash with the eye colours. The BIDS export writes ``AverageCalibrationError``
and ``MaximalCalibrationError`` (accuracy, in degrees) to each eye's
``*_physio.json``, along with ``CalibrationType``, ``CalibrationPosition`` and
``CalibrationCount``. ETM calibrations and skipped validations have no quality
numbers.

Study tolerance
~~~~~~~~~~~~~~~

A calibration is good enough when, in **at least one eye**, the **worst
validation target's error is at most 2.5°** (``max_accuracy_deg``, the largest
per-target accuracy). In other words, every target, including each screen
corner, has to be within 2.5°.

Why the worst target, not the mean: what matters is that gaze is accurate
across the whole screen, out to its extremities. A mean over targets can hide
one bad corner; for example, a validation with a mean of 1.3° can still have a
corner off by 3.1°, and that calibration fails.

The 2.5° value and the at-least-one-eye rule come from ABCCT ("calibration
error < 2.5°", ABCCT ET MOP v5.1 and Shic et al. 2022). ABCCT applied it to a
mean error, per trial during the tasks; aria-et applies it to the worst target,
at validation right after calibrating, which is stricter. Accuracy tends to
worsen during a session, so this is a minimum bar. Precision, data loss and
the mean accuracy are shown for information only.

Under the table, a short verdict says what to do: "Within 2.5° tolerance: OK
to proceed" (green on the stimulus screen) or "Above 2.5° tolerance:
re-calibrate (C)" (amber; the GUI shows it as a warning banner, without the
key). Each history entry ends with "within tolerance" or "above tolerance". The verdict is also saved in
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

Live child position (GUI)
-------------------------

The GUI shows a **Child position** panel under the page list, on every page.
It is the same picture as DeToX's positioning screen, but it stays live during
calibration and runs, so the operator can see if the child slumps, leans in or
turns away:

- the tracker's **track box** with a dot per eye (left eye blue, right eye
  pink; mirrored like DeToX, as if facing the child),
- a **distance bar** from *near* to *far*, with the ideal distance marked and
  the good range shaded,
- a status: **Position good**, **Too close**, **Too far**, **Move to centre**,
  **Eyes not found**, **No position data** (no recent samples) or
  **No tracker**.

It starts after a successful **Check tracker** on the Hardware page and uses
the tracker saved for this laptop. It shows where the tracker sees the eyes,
not where the child is looking. The GUI reads the tracker's user position
stream itself, alongside the calibration or task process; this costs very
little and doesn't touch the recording.

The thresholds (ideal distance, good range, centre band) are starting values
in ``aria_et/calibration.py`` (``POSITION_*``) and should be tuned on the lab
hardware, including confirming that the distance runs near to far.
