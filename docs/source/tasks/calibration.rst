.. _task-calibration:

Child-Friendly Calibration
==========================

Preview
-------

.. vimeo:: 1214478085

`Child-friendly calibration video <https://vimeo.com/1214478085>`__

Description
-----------

The child-friendly calibration routine presents a five-point calibration
sequence using the Gap-Overlap reward animations and auditory stimuli. The
target positions are center, top-left, top-right, bottom-right, and bottom-left.
By default the target inset is ``0.1`` in normalized display coordinates. In a
tracker-connected calibration, the stimulus initially spins to attract gaze and
then shrinks during collection feedback after gaze reaches the target.

Event Markers
-------------

The markers below are emitted as ``RuntimeEvent.name`` values by the calibration
presenter.

.. list-table::
   :header-rows: 1
   :widths: 30 40 30

   * - Marker
     - Meaning
     - Payload fields
   * - ``calibration.started``
     - Calibration sequence began.
     - ``sequence_id``
   * - ``calibration.point.started``
     - A calibration target point was presented.
     - ``label``, ``x``, ``y``, ``window_x``, ``window_y``
   * - ``calibration.point.ended``
     - The current calibration target point completed.
     - ``label``
   * - ``calibration.aborted``
     - Calibration stopped before all points completed.
     - ``sequence_id``, ``point_count``
   * - ``calibration.ended``
     - Calibration sequence ended.
     - ``sequence_id``, ``point_count``
