# Overview Close

Role: return the result to its surrounding context. Appearance: full UI and a
closing message. Inputs: final state, full-view pose and approved message.
Motion: pull back from the last focus while preserving the window and selected
state, then reveal the message. QA: camera never resets the result, no clipping
or message/control collision, full view and final frame read clearly.
