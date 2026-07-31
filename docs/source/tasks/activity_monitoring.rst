.. _task-activity-monitoring:

Activity Monitoring
===================

.. image:: ../../../src/aria_et/assets/abcct/activity-monitoring/images/ams_a0_s3_b3_gm_d1_f1.jpg
   :alt: Activity Monitoring static-image stimulus example

Preview
-------

.. vimeo:: 1214478084

`Activity Monitoring video <https://vimeo.com/1214478084>`__

Description
-----------

Activity Monitoring presents 16 trials across four blocks. Trials alternate
between dynamic videos and static images depicting activity-gaze and mutual-gaze
conditions. Dynamic-video trials are presented for 20 seconds, static-image
trials are presented for 10 seconds, and a one-second blank inter-trial interval
is inserted between trials.

Static-image trials play the task soundtrack. Dynamic-video trials use the
embedded movie audio.

Event Markers
-------------

The markers below are emitted as ``RuntimeEvent.name`` values by the Activity
Monitoring presenter.

.. list-table::
   :header-rows: 1
   :widths: 35 35 30

   * - Marker
     - Meaning
     - Payload fields
   * - ``activity-monitoring.started``
     - Task sequence began.
     - ``sequence_id``
   * - ``activity-monitoring.trial.started``
     - A trial began, before fixation and stimulus presentation.
     - ``trial_id``, ``media_type``, ``gaze_condition``, ``media``
   * - ``activity-monitoring.trial.ended``
     - The trial completed.
     - ``trial_id``
   * - ``activity-monitoring.inter-trial-interval.started``
     - Blank inter-trial interval began.
     - ``duration_seconds``
   * - ``activity-monitoring.inter-trial-interval.ended``
     - Blank inter-trial interval ended.
     - ``duration_seconds``
   * - ``activity-monitoring.ended``
     - Task sequence ended.
     - ``sequence_id``, ``trial_count``

Payload Field Reference
-----------------------

.. list-table::
   :header-rows: 1
   :widths: 25 55 20

   * - Field
     - Description
     - Example or values
   * - ``sequence_id``
     - Task sequence identifier.
     - ``activity-monitoring``
   * - ``trial_id``
     - Trial identifier assigned by sequence order.
     - ``am-01`` through ``am-16``
   * - ``media_type``
     - Stimulus presentation type.
     - ``dynamic-video`` or ``static-image``
   * - ``gaze_condition``
     - Social gaze condition represented by the stimulus.
     - ``activity-gaze`` or ``mutual-gaze``
   * - ``media``
     - Bundled stimulus filename presented on that trial.
     - ``.mp4`` for dynamic-video trials; ``.jpg`` for static-image trials
   * - ``duration_seconds``
     - Duration of the blank inter-trial interval.
     - ``1.0``
   * - ``trial_count``
     - Number of trials completed before the task ended.
     - Integer from ``0`` to ``16``
