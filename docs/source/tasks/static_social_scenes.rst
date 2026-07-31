.. _task-static-social-scenes:

Static Social Scenes
====================

.. image:: ../../../src/aria_et/assets/abcct/static-social-scenes/images/popout1_f0.jpg
   :alt: Static Social Scenes visual-search stimulus example

Preview
-------

.. vimeo:: 1214478098

`Static Social Scenes video <https://vimeo.com/1214478098>`__

Description
-----------

Static Social Scenes presents 12 trials across two blocks. The sequence includes
six static-scene trials and six visual-search trials. Static-scene trials use a
black background and are presented for 20 seconds. Visual-search trials use a
white background and are presented for 12 seconds. Each trial has a specified
soundtrack that starts with the image and is stopped at trial end.

Event Markers
-------------

The markers below are emitted as ``RuntimeEvent.name`` values by the Static
Social Scenes presenter.

.. list-table::
   :header-rows: 1
   :widths: 35 35 30

   * - Marker
     - Meaning
     - Payload fields
   * - ``static-social-scenes.started``
     - Task sequence began.
     - ``sequence_id``
   * - ``static-social-scenes.trial.started``
     - A trial began.
     - ``trial_id``, ``trial_type``, ``image``, ``soundtrack``, ``background_rgb``
   * - ``static-social-scenes.trial.ended``
     - The trial completed.
     - ``trial_id``
   * - ``static-social-scenes.ended``
     - Task sequence ended.
     - ``sequence_id``, ``trial_count``
