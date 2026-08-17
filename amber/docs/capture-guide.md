# Capture guide

This guide is part of the product, not an afterthought. Amber can only preserve
what your camera actually saw from enough angles; nothing in processing can
recover a viewpoint you never recorded.

## The one thing that matters most

**Walk. Do not pivot.**

Standing in one place and panning produces zero parallax, and without parallax
there is no depth to reconstruct. Amber detects this and reports
`insufficient_translation` rather than producing something that looks like a
scene but is not one.

## Recommended capture

- Use the rear **1× main camera**. Do not zoom and do not switch lenses
  mid-take — a lens switch changes the intrinsics halfway through.
- Record **4K/30** if convenient; 1080p/30 is fine. Amber downsamples for
  training but keeps full resolution for camera solving.
- Use ordinary **Video** mode, not Cinematic.
- Before recording, touch and hold your main subject until **AE/AF Lock**
  appears. Set exposure for the part of the scene that matters, then leave it
  fixed for the whole pass. If a bright window has to blow out to keep the
  interior consistent, accept that — consistency across views matters more than
  perfect exposure in any one view.
- Record for **30–90 seconds**, depending on scene size.
- Walk slowly around or through the subject, translating the phone through
  space.
- Keep **large overlaps** between consecutive views. Every surface should stay
  visible across many neighbouring viewpoints.
- Make **at least one loop**, or revisit an angle you already covered. This is
  what ties the reconstruction together.
- Use steady, diffuse light. Avoid motion blur and exposure pumping.
- For a person: ask them to hold one comfortable pose. Breathing and eye
  movement can still create artifacts, and Amber will require a human review
  before calling the result a success.

### Advanced, optional

Apple's **Final Cut Camera** lets you fix lens, focus, exposure, and white
balance manually. It produces the most controlled capture, but it is not
required.

### If physical scale matters

Place a clearly visible known-size reference near the edge of the scene — a
30 cm ruler or a printed A4 sheet — and keep it visible from several angles.
Crop it out of the presentation later. Do not use a credit card for a
room-scale capture; it is too small to measure against.

Monocular video contains no absolute scale. Until you calibrate with a known
distance, "human scale" means comfortable relative navigation, and Amber's
interface will not claim otherwise.

## Known hard cases

**Surfaces that confuse matching:** mirrors, windows, glossy appliances, fine
repeating patterns, blank white walls, smoke, fire, translucent objects.

**Things that move while you film:** wind-blown leaves, water, traffic, pets,
children. Static 3DGS assumes a static world; a moving subject becomes ghosting
or smearing.

**Camera problems:** pure rotation from one position, autofocus hunting, digital
zoom, lens switching, heavy low-light noise, substantial motion blur.

## When a capture fails

A failed capture stays in the project with its diagnostic report, so you can see
what went wrong and learn from it. Amber warns; it does not scold.

Common diagnostics and what they mean:

| Diagnostic | What happened | What to do |
| --- | --- | --- |
| `insufficient_translation` | The camera rotated but barely moved | Walk around the subject while recording |
| `insufficient_parallax` | Views were nearly the same direction | Vary your position more widely |
| `fragmented_reconstruction` | The capture broke into disconnected pieces | Revisit an earlier angle mid-capture |
| `low_registration_ratio` | Too few views could be linked | Move more slowly; check light and blur |
| `insufficient_registered_frames` | Not enough usable views for this scene size | Record for longer |
| `temporal_gap_exceeded` | A long stretch could not be tracked | Slow down through that part of the path |
| `mapper_initialization_failed` | No reliable starting pair of views | Usually the same cause as the two above |
