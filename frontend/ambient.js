(() => {
  const canvas = document.querySelector("#ambient-canvas");
  if (!canvas) return;

  const context = canvas.getContext("2d", { alpha: true });
  if (!context) return;

  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  const colors = ["#f9f3b9", "#c9a453", "#823c30", "#441811"];
  const interactionGain = 1.2;
  const maximumEnergy = 4.2;
  const maximumVelocity = 5.5 * interactionGain;
  const maximumSpin = 0.018 * interactionGain;
  const translationImpulse = 1.05 * interactionGain;
  const spinImpulse = 0.0032 * interactionGain;
  const cube = {
    points: [
      [-1, -1, -1], [1, -1, -1], [1, 1, -1], [-1, 1, -1],
      [-1, -1, 1], [1, -1, 1], [1, 1, 1], [-1, 1, 1],
    ],
    edges: [
      [0, 1], [1, 2], [2, 3], [3, 0], [4, 5], [5, 6],
      [6, 7], [7, 4], [0, 4], [1, 5], [2, 6], [3, 7],
    ],
  };
  const octahedron = {
    points: [[1, 0, 0], [-1, 0, 0], [0, 1, 0], [0, -1, 0], [0, 0, 1], [0, 0, -1]],
    edges: [
      [0, 2], [0, 3], [0, 4], [0, 5], [1, 2], [1, 3],
      [1, 4], [1, 5], [2, 4], [2, 5], [3, 4], [3, 5],
    ],
  };

  const forms = [
    makeForm("cube", 0.09, 0.34, 0.12, 0, 0.21),
    makeForm("rings", 0.9, 0.31, 0.145, 1, 0.2),
    makeForm("octahedron", 0.17, 0.78, 0.1, 2, 0.18),
    makeForm("cube", 0.82, 0.79, 0.13, 3, 0.18),
    makeForm("rings", 0.51, 0.61, 0.17, 1, 0.105),
    makeForm("mandsaab", 0.72, 0.72, 0.12, 1, 0.17),
  ];

  const motes = Array.from({ length: 30 }, (_, index) => ({
    x: seeded(index * 3 + 1),
    y: seeded(index * 3 + 2),
    depth: 0.25 + seeded(index * 3 + 3) * 0.75,
    phase: seeded(index * 7 + 4) * Math.PI * 2,
  }));

  let width = 0;
  let height = 0;
  let pixelRatio = 1;
  let animationFrame;
  let previousFrame = performance.now();
  let previousPointer = { x: window.innerWidth / 2, y: window.innerHeight / 2, time: performance.now() };
  let pointer = { x: 0, y: 0 };
  let dragState = null;

  function makeForm(kind, x, y, size, colorIndex, opacity) {
    return {
      kind,
      x,
      y,
      size,
      color: colors[colorIndex],
      opacity,
      rotationX: x * Math.PI,
      rotationY: y * Math.PI,
      rotationZ: (x + y) * 0.7,
      offsetX: 0,
      offsetY: 0,
      velocityX: 0,
      velocityY: 0,
      spinX: 0,
      spinY: 0,
      screenX: 0,
      screenY: 0,
      screenSize: 0,
      dragging: false,
    };
  }

  function seeded(value) {
    const result = Math.sin(value * 92.317) * 43758.5453;
    return result - Math.floor(result);
  }

  function resize() {
    width = window.innerWidth;
    height = window.innerHeight;
    pixelRatio = Math.min(window.devicePixelRatio || 1, 1.75);
    canvas.width = Math.round(width * pixelRatio);
    canvas.height = Math.round(height * pixelRatio);
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;
    context.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0);

    if (reducedMotion.matches) draw(performance.now(), 0);
  }

  function logarithmicImpulse(velocityX, velocityY, strength = 1) {
    const speed = Math.hypot(velocityX, velocityY);
    if (speed < 1) return { x: 0, y: 0, spinX: 0, spinY: 0 };

    // One shared logarithmic transfer curve powers both cursor pushes and
    // drag releases. The gain makes travel 20% stronger while the logarithm
    // and clamps keep hard flings controlled.
    const energy = Math.min(maximumEnergy, Math.log1p(speed / 120)) * strength;
    const directionX = velocityX / speed;
    const directionY = velocityY / speed;

    return {
      x: directionX * energy * translationImpulse,
      y: directionY * energy * translationImpulse,
      spinX: -directionY * energy * spinImpulse,
      spinY: directionX * energy * spinImpulse,
    };
  }

  function applyImpulse(form, impulse, replace = false) {
    form.velocityX = clamp((replace ? 0 : form.velocityX) + impulse.x, -maximumVelocity, maximumVelocity);
    form.velocityY = clamp((replace ? 0 : form.velocityY) + impulse.y, -maximumVelocity, maximumVelocity);
    form.spinX = clamp((replace ? 0 : form.spinX) + impulse.spinX, -maximumSpin, maximumSpin);
    form.spinY = clamp((replace ? 0 : form.spinY) + impulse.spinY, -maximumSpin, maximumSpin);
  }

  function isInteractiveTarget(target) {
    return target instanceof Element && Boolean(target.closest(
      "input, textarea, button, a, video, .condense-card, .progress-zone, .title-banner, .result-stage",
    ));
  }

  function hitTestForm(clientX, clientY) {
    let match = null;
    let bestDistance = Infinity;

    forms.forEach((form) => {
      if (form.screenSize <= 0) return;
      const distance = Math.hypot(clientX - form.screenX, clientY - form.screenY);
      const radius = Math.max(58, form.screenSize * 1.22);
      const normalizedDistance = distance / radius;
      if (normalizedDistance <= 1 && normalizedDistance < bestDistance) {
        bestDistance = normalizedDistance;
        match = form;
      }
    });

    return match;
  }

  function updateHoverCursor(event) {
    const canGrab = !reducedMotion.matches
      && !dragState
      && !isInteractiveTarget(event.target)
      && Boolean(hitTestForm(event.clientX, event.clientY));
    document.documentElement.classList.toggle("ambient-hover", canGrab);
  }

  function onPointerDown(event) {
    if (
      dragState
      || reducedMotion.matches
      || event.pointerType === "touch"
      || event.button !== 0
      || isInteractiveTarget(event.target)
    ) return;

    const form = hitTestForm(event.clientX, event.clientY);
    if (!form) return;

    const now = performance.now();
    const captureTarget = event.target instanceof Element ? event.target : null;
    event.preventDefault();
    captureTarget?.setPointerCapture?.(event.pointerId);
    form.dragging = true;
    form.velocityX = 0;
    form.velocityY = 0;
    dragState = {
      form,
      pointerId: event.pointerId,
      lastX: event.clientX,
      lastY: event.clientY,
      lastTime: now,
      lastMovementAt: now,
      releaseVelocityX: 0,
      releaseVelocityY: 0,
      moved: false,
      captureTarget,
    };
    previousPointer = { x: event.clientX, y: event.clientY, time: now };
    document.documentElement.classList.remove("ambient-hover");
    document.documentElement.classList.add("ambient-dragging");
  }

  function onPointerMove(event) {
    const now = performance.now();
    const elapsed = Math.max(8, now - previousPointer.time);
    const deltaX = event.clientX - previousPointer.x;
    const deltaY = event.clientY - previousPointer.y;

    pointer.x = (event.clientX / Math.max(1, width) - 0.5) * 2;
    pointer.y = (event.clientY / Math.max(1, height) - 0.5) * 2;

    if (dragState && event.pointerId === dragState.pointerId) {
      const dragElapsed = Math.max(8, now - dragState.lastTime);
      const dragDeltaX = event.clientX - dragState.lastX;
      const dragDeltaY = event.clientY - dragState.lastY;
      const movement = Math.hypot(dragDeltaX, dragDeltaY);
      const minimumCenterMargin = 34;
      const form = dragState.form;

      event.preventDefault();
      form.offsetX = clamp(
        form.offsetX + dragDeltaX,
        -form.x * width + minimumCenterMargin,
        (1 - form.x) * width - minimumCenterMargin,
      );
      form.offsetY = clamp(
        form.offsetY + dragDeltaY,
        -form.y * height + minimumCenterMargin,
        (1 - form.y) * height - minimumCenterMargin,
      );

      if (movement > 0.35) {
        const instantaneousX = (dragDeltaX / dragElapsed) * 1000;
        const instantaneousY = (dragDeltaY / dragElapsed) * 1000;
        const sampleWeight = dragState.moved ? 0.42 : 1;
        dragState.releaseVelocityX += (instantaneousX - dragState.releaseVelocityX) * sampleWeight;
        dragState.releaseVelocityY += (instantaneousY - dragState.releaseVelocityY) * sampleWeight;
        dragState.lastMovementAt = now;
        dragState.moved = true;
      }

      dragState.lastX = event.clientX;
      dragState.lastY = event.clientY;
      dragState.lastTime = now;
      previousPointer = { x: event.clientX, y: event.clientY, time: now };
      return;
    }

    if (dragState) return;

    updateHoverCursor(event);
    if (reducedMotion.matches) {
      previousPointer = { x: event.clientX, y: event.clientY, time: now };
      return;
    }

    const cursorVelocityX = (deltaX / elapsed) * 1000;
    const cursorVelocityY = (deltaY / elapsed) * 1000;

    forms.forEach((form) => {
      const distance = Math.hypot(event.clientX - form.screenX, event.clientY - form.screenY);
      const reach = Math.max(145, form.screenSize * 1.75);
      if (form.dragging || distance >= reach) return;

      const proximity = Math.pow(1 - distance / reach, 2);
      applyImpulse(form, logarithmicImpulse(cursorVelocityX, cursorVelocityY, proximity));
    });

    previousPointer = { x: event.clientX, y: event.clientY, time: now };
  }

  function endDrag(event, launch) {
    if (!dragState || (event?.pointerId !== undefined && event.pointerId !== dragState.pointerId)) return;

    const state = dragState;
    const now = performance.now();
    const idleMilliseconds = Math.max(0, now - state.lastMovementAt);
    const releaseDecay = Math.exp(-idleMilliseconds / 145);
    state.form.dragging = false;

    if (state.captureTarget?.hasPointerCapture?.(state.pointerId)) {
      state.captureTarget.releasePointerCapture(state.pointerId);
    }

    if (launch && state.moved) {
      const releaseVelocityX = state.releaseVelocityX * releaseDecay;
      const releaseVelocityY = state.releaseVelocityY * releaseDecay;
      applyImpulse(state.form, logarithmicImpulse(releaseVelocityX, releaseVelocityY), true);
    }

    dragState = null;
    document.documentElement.classList.remove("ambient-dragging");
    document.documentElement.classList.remove("ambient-hover");

    if (event?.clientX !== undefined) {
      previousPointer = { x: event.clientX, y: event.clientY, time: now };
      updateHoverCursor(event);
    }
  }

  function clamp(value, minimum, maximum) {
    return Math.max(minimum, Math.min(maximum, value));
  }

  function rotate(point, rotationX, rotationY, rotationZ) {
    let [x, y, z] = point;

    const cosX = Math.cos(rotationX);
    const sinX = Math.sin(rotationX);
    [y, z] = [y * cosX - z * sinX, y * sinX + z * cosX];

    const cosY = Math.cos(rotationY);
    const sinY = Math.sin(rotationY);
    [x, z] = [x * cosY + z * sinY, -x * sinY + z * cosY];

    const cosZ = Math.cos(rotationZ);
    const sinZ = Math.sin(rotationZ);
    [x, y] = [x * cosZ - y * sinZ, x * sinZ + y * cosZ];

    return [x, y, z];
  }

  function project(point, centerX, centerY, scale) {
    const depth = 4.2 + point[2];
    const perspective = 3.5 / Math.max(1.7, depth);
    return {
      x: centerX + point[0] * scale * perspective,
      y: centerY + point[1] * scale * perspective,
      depth: perspective,
    };
  }

  function updateForm(form, frameScale) {
    const spring = 0.014 * frameScale;
    const damping = Math.pow(0.91, frameScale);

    if (!form.dragging) {
      form.velocityX += -form.offsetX * spring * 0.045;
      form.velocityY += -form.offsetY * spring * 0.045;
      form.velocityX *= damping;
      form.velocityY *= damping;
      form.offsetX += form.velocityX * frameScale;
      form.offsetY += form.velocityY * frameScale;
    }

    form.spinX *= Math.pow(0.955, frameScale);
    form.spinY *= Math.pow(0.955, frameScale);
    form.rotationX += (0.0012 + form.spinX) * frameScale;
    form.rotationY += (0.0018 + form.spinY) * frameScale;
    form.rotationZ += 0.00045 * frameScale;
  }

  function drawGeometry(form, geometry, centerX, centerY, scale) {
    const projected = geometry.points.map((point) =>
      project(rotate(point, form.rotationX, form.rotationY, form.rotationZ), centerX, centerY, scale),
    );

    context.beginPath();
    geometry.edges.forEach(([start, end]) => {
      context.moveTo(projected[start].x, projected[start].y);
      context.lineTo(projected[end].x, projected[end].y);
    });
    context.stroke();

    projected.forEach((point) => {
      context.beginPath();
      context.arc(point.x, point.y, Math.max(0.8, point.depth * 1.5), 0, Math.PI * 2);
      context.fill();
    });
  }

  function drawRings(form, centerX, centerY, scale) {
    for (let ring = 0; ring < 3; ring += 1) {
      context.beginPath();
      const pointCount = 44;
      for (let index = 0; index <= pointCount; index += 1) {
        const angle = (index / pointCount) * Math.PI * 2;
        const radius = 1 - ring * 0.19;
        const source = [
          Math.cos(angle) * radius,
          Math.sin(angle) * radius,
          Math.sin(angle * 2 + ring) * 0.12,
        ];
        const point = project(
          rotate(source, form.rotationX + ring * 0.48, form.rotationY + ring * 0.58, form.rotationZ),
          centerX,
          centerY,
          scale,
        );
        if (index === 0) context.moveTo(point.x, point.y);
        else context.lineTo(point.x, point.y);
      }
      context.stroke();
    }
  }

  function drawMandSaab(form, centerX, centerY, scale) {
    context.save();
    context.translate(centerX, centerY);
    context.rotate(form.rotationZ * 0.16);
    context.font = `700 ${Math.max(24, scale * 0.52)}px "Manrope", sans-serif`;
    context.textAlign = "center";
    context.textBaseline = "middle";
    context.lineWidth = Math.max(1, scale * 0.012);
    context.strokeText("MandSaab", 0, 0);
    context.restore();
  }

  function drawMotes(time) {
    motes.forEach((mote, index) => {
      const drift = Math.sin(time * 0.00018 + mote.phase) * 9 * mote.depth;
      const x = mote.x * width + pointer.x * 9 * mote.depth;
      const y = (mote.y * height + drift + index * 0.3) % height;
      const radius = 0.6 + mote.depth * 1.25;
      context.globalAlpha = 0.035 + mote.depth * 0.055;
      context.fillStyle = index % 3 === 0 ? colors[0] : colors[1];
      context.beginPath();
      context.arc(x, y, radius, 0, Math.PI * 2);
      context.fill();
    });
  }

  function draw(time, frameScale) {
    context.clearRect(0, 0, width, height);
    drawMotes(time);

    forms.forEach((form, index) => {
      if (frameScale) updateForm(form, frameScale);

      const baseScale = Math.min(width, height) * form.size;
      const parallax = 8 + index * 2.5;
      const centerX = form.x * width + form.offsetX + pointer.x * parallax;
      const centerY = form.y * height + form.offsetY + pointer.y * parallax * 0.65;

      form.screenX = centerX;
      form.screenY = centerY;
      form.screenSize = baseScale;

      context.save();
      context.strokeStyle = form.color;
      context.fillStyle = form.color;
      context.globalAlpha = form.opacity;
      context.lineWidth = Math.max(0.75, Math.min(1.35, width / 1300));
      context.shadowColor = form.color;
      context.shadowBlur = 12;

      if (form.kind === "rings") drawRings(form, centerX, centerY, baseScale);
      else if (form.kind === "mandsaab") drawMandSaab(form, centerX, centerY, baseScale);
      else drawGeometry(form, form.kind === "cube" ? cube : octahedron, centerX, centerY, baseScale);

      context.restore();
    });

    context.globalAlpha = 1;
  }

  function animate(now) {
    const elapsed = Math.min(40, now - previousFrame);
    previousFrame = now;
    draw(now, elapsed / (1000 / 60));
    animationFrame = requestAnimationFrame(animate);
  }

  function start() {
    cancelAnimationFrame(animationFrame);
    previousFrame = performance.now();
    if (reducedMotion.matches) {
      draw(previousFrame, 0);
      return;
    }
    animationFrame = requestAnimationFrame(animate);
  }

  function onReducedMotionChange() {
    if (reducedMotion.matches) endDrag(undefined, false);
    start();
  }

  window.addEventListener("resize", resize, { passive: true });
  window.addEventListener("pointerdown", onPointerDown, { passive: false });
  window.addEventListener("pointermove", onPointerMove, { passive: false });
  window.addEventListener("pointerup", (event) => endDrag(event, true), { passive: true });
  window.addEventListener("pointercancel", (event) => endDrag(event, false), { passive: true });
  window.addEventListener("blur", () => endDrag(undefined, false));
  document.documentElement.addEventListener("pointerleave", () => {
    if (!dragState) document.documentElement.classList.remove("ambient-hover");
  });
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) {
      endDrag(undefined, false);
      cancelAnimationFrame(animationFrame);
    }
    else start();
  });
  reducedMotion.addEventListener?.("change", onReducedMotionChange);

  resize();
  start();
})();
