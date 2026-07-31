.. _task-social-interactive:

Social Interactive
==================

Preview
-------

.. vimeo:: 1214478083

`Social Interactive video <https://vimeo.com/1214478083>`__

Description
-----------

Social Interactive presents 22 video trials across four blocks. The task
includes 11 parallel-play trials and 11 cooperative-play trials. Each video is
presented for 15 seconds after a one-second fixation interval, followed by a
0.25-second blank interval.

Event Markers
-------------

The markers below are emitted as ``RuntimeEvent.name`` values by the Social
Interactive presenter.

.. list-table::
   :header-rows: 1
   :widths: 35 35 30

   * - Marker
     - Meaning
     - Payload fields
   * - ``social-interactive.started``
     - Task sequence began.
     - ``sequence_id``
   * - ``social-interactive.trial.started``
     - A trial began, before fixation and video presentation.
     - ``trial_id``, ``block_id``, ``block_number``, ``block_trial_number``, ``sequence_trial_number``, ``source_id``, ``play_condition``, ``video``
   * - ``social-interactive.trial.ended``
     - The trial completed.
     - ``trial_id``
   * - ``social-interactive.ended``
     - Task sequence ended.
     - ``sequence_id``, ``trial_count``
