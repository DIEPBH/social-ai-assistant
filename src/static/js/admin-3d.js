/**
 * Social AI Assistant - 3D WebGL Neural Scene & Interactive Effects for Admin
 * Matrix / Cyber Security Green Theme
 * Powered by Three.js
 */

(function () {
  'use strict';

  // --- Ensure 3D Canvas Container Exists in DOM ---
  function ensureCanvasContainer() {
    let container = document.getElementById('canvas-container');
    if (!container) {
      container = document.createElement('div');
      container.id = 'canvas-container';
      document.body.prepend(container);
    }
    return container;
  }

  // --- Dynamic Loader for Three.js if not already present ---
  function loadThreeJs(callback) {
    if (typeof THREE !== 'undefined') {
      callback();
      return;
    }

    const script = document.createElement('script');
    script.src = 'https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js';
    script.async = true;
    script.onload = function () {
      callback();
    };
    script.onerror = function () {
      console.warn('Could not load Three.js from CDN.');
    };
    document.head.appendChild(script);
  }

  // --- Three.js 3D Neural Scene Engine ---
  let scene, camera, renderer;
  let particlesGroup, neuralSphereGroup, orbitRingGroup;
  let mouseX = 0, mouseY = 0;
  let targetX = 0, targetY = 0;
  let windowHalfX = window.innerWidth / 2;
  let windowHalfY = window.innerHeight / 2;
  let isInitialized = false;

  function initThreeScene() {
    if (isInitialized) return;
    const container = ensureCanvasContainer();

    if (!container || typeof THREE === 'undefined') {
      return;
    }

    isInitialized = true;

    // 1. Create Scene & Camera
    scene = new THREE.Scene();
    camera = new THREE.PerspectiveCamera(55, window.innerWidth / window.innerHeight, 1, 2000);
    camera.position.z = 850;

    // 2. Create Renderer
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: 'high-performance' });
    } catch (e) {
      console.warn('WebGL not supported:', e);
      return;
    }

    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    container.innerHTML = '';
    container.appendChild(renderer.domElement);

    // 3. Ambient Floating Cyber Nebula Particles (600 particles)
    const particleCount = 600;
    const particleGeometry = new THREE.BufferGeometry();
    const positions = new Float32Array(particleCount * 3);
    const colors = new Float32Array(particleCount * 3);

    const colorGreenPrimary = new THREE.Color(0x00e676); // Neon Matrix Green
    const colorGreenDeep = new THREE.Color(0x00a152);    // Police Green
    const colorGold = new THREE.Color(0xf59e0b);         // Amber Gold Accent

    for (let i = 0; i < particleCount; i++) {
      positions[i * 3] = (Math.random() - 0.5) * 1800;
      positions[i * 3 + 1] = (Math.random() - 0.5) * 1400;
      positions[i * 3 + 2] = (Math.random() - 0.5) * 1400;

      const mixedColor = i % 4 === 0 ? colorGold : (i % 2 === 0 ? colorGreenPrimary : colorGreenDeep);
      colors[i * 3] = mixedColor.r;
      colors[i * 3 + 1] = mixedColor.g;
      colors[i * 3 + 2] = mixedColor.b;
    }

    particleGeometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    particleGeometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));

    const particleMaterial = new THREE.PointsMaterial({
      size: 4,
      vertexColors: true,
      transparent: true,
      opacity: 0.8,
      blending: THREE.AdditiveBlending
    });

    particlesGroup = new THREE.Points(particleGeometry, particleMaterial);
    scene.add(particlesGroup);

    // 4. Interactive Neural Sphere (Clean & Sharp Geometry)
    neuralSphereGroup = new THREE.Group();

    // Core Icosahedron Wireframe
    const icoGeo = new THREE.IcosahedronGeometry(220, 2);
    const icoMat = new THREE.MeshBasicMaterial({
      color: 0x00e676,
      wireframe: true,
      transparent: true,
      opacity: 0.35
    });
    const icoMesh = new THREE.Mesh(icoGeo, icoMat);
    neuralSphereGroup.add(icoMesh);

    // Nodes on sphere vertices
    const icoPos = icoGeo.attributes.position;
    const nodeCount = icoPos.count;
    const nodeGeo = new THREE.BufferGeometry();
    const nodePositions = new Float32Array(nodeCount * 3);

    for (let i = 0; i < nodeCount; i++) {
      nodePositions[i * 3] = icoPos.getX(i);
      nodePositions[i * 3 + 1] = icoPos.getY(i);
      nodePositions[i * 3 + 2] = icoPos.getZ(i);
    }
    nodeGeo.setAttribute('position', new THREE.BufferAttribute(nodePositions, 3));

    const nodeMat = new THREE.PointsMaterial({
      color: 0xffffff,
      size: 6,
      transparent: true,
      opacity: 0.95,
      blending: THREE.AdditiveBlending
    });
    const nodesMesh = new THREE.Points(nodeGeo, nodeMat);
    neuralSphereGroup.add(nodesMesh);

    // Position sphere
    if (window.innerWidth > 992) {
      neuralSphereGroup.position.set(280, 0, -60);
    } else {
      neuralSphereGroup.position.set(0, -40, -100);
      neuralSphereGroup.scale.set(0.75, 0.75, 0.75);
    }
    scene.add(neuralSphereGroup);

    // 5. Orbiting Data Rings
    orbitRingGroup = new THREE.Group();
    const ringGeo1 = new THREE.RingGeometry(320, 322, 64);
    const ringMat1 = new THREE.MeshBasicMaterial({
      color: 0x00e676,
      side: THREE.DoubleSide,
      transparent: true,
      opacity: 0.45
    });
    const ringMesh1 = new THREE.Mesh(ringGeo1, ringMat1);
    ringMesh1.rotation.x = Math.PI / 3;
    ringMesh1.rotation.y = Math.PI / 6;
    orbitRingGroup.add(ringMesh1);

    const ringGeo2 = new THREE.RingGeometry(360, 362, 64);
    const ringMat2 = new THREE.MeshBasicMaterial({
      color: 0xf59e0b,
      side: THREE.DoubleSide,
      transparent: true,
      opacity: 0.35
    });
    const ringMesh2 = new THREE.Mesh(ringGeo2, ringMat2);
    ringMesh2.rotation.x = -Math.PI / 4;
    ringMesh2.rotation.y = -Math.PI / 4;
    orbitRingGroup.add(ringMesh2);

    neuralSphereGroup.add(orbitRingGroup);

    // Event Listeners
    window.addEventListener('resize', onWindowResize, { passive: true });
    document.addEventListener('mousemove', onDocumentMouseMove, { passive: true });

    animate();
  }

  function onWindowResize() {
    if (!renderer || !camera) return;
    windowHalfX = window.innerWidth / 2;
    windowHalfY = window.innerHeight / 2;
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);

    if (neuralSphereGroup) {
      if (window.innerWidth > 992) {
        neuralSphereGroup.position.set(280, 0, -60);
        neuralSphereGroup.scale.set(1, 1, 1);
      } else {
        neuralSphereGroup.position.set(0, -40, -100);
        neuralSphereGroup.scale.set(0.75, 0.75, 0.75);
      }
    }
  }

  function onDocumentMouseMove(event) {
    mouseX = (event.clientX - windowHalfX);
    mouseY = (event.clientY - windowHalfY);
  }

  function animate() {
    requestAnimationFrame(animate);

    targetX += (mouseX - targetX) * 0.03;
    targetY += (mouseY - targetY) * 0.03;

    if (particlesGroup) {
      particlesGroup.rotation.y += 0.0006;
      particlesGroup.rotation.x += 0.0003;
    }

    if (neuralSphereGroup) {
      neuralSphereGroup.rotation.y += 0.003;
      neuralSphereGroup.rotation.x = targetY * 0.0004;
      neuralSphereGroup.rotation.z = targetX * 0.0004;
    }

    if (orbitRingGroup) {
      orbitRingGroup.rotation.z += 0.005;
    }

    if (camera) {
      camera.position.x += (targetX * 0.2 - camera.position.x) * 0.03;
      camera.position.y += (-targetY * 0.2 - camera.position.y) * 0.03;
      camera.lookAt(scene.position);
    }

    if (renderer && scene && camera) {
      renderer.render(scene, camera);
    }
  }

  // --- 3D Card Tilt (ONLY for small HUD / KPI / Login Cards, NEVER for Data Tables & Changelists) ---
  function initCardTilt() {
    // Select strictly designated HUD cards
    const tiltCards = document.querySelectorAll('.tilt-card, .kpi-card, .tilt-box, .status-hud-card');

    tiltCards.forEach(card => {
      // NEVER tilt if element is or contains tables, forms, or changelist
      if (card.querySelector('table, form, #changelist, .results, .change-list') || 
          card.closest('#changelist, .change-list, #changelist-form, .module, .change-form, table, form')) {
        return;
      }

      let bounds;

      function rotateToMouse(e) {
        bounds = card.getBoundingClientRect();
        const mouseX = e.clientX - bounds.left;
        const mouseY = e.clientY - bounds.top;
        const leftX = mouseX - bounds.width / 2;
        const topY = mouseY - bounds.height / 2;

        const intensity = 5;
        const rotateX = (topY / (bounds.height / 2)) * -intensity;
        const rotateY = (leftX / (bounds.width / 2)) * intensity;

        card.style.transform = `perspective(1000px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) translateY(-2px)`;

        // Move glow spot if exists
        const glowSpot = card.querySelector('.card-glow-spot');
        if (glowSpot) {
          glowSpot.style.opacity = '1';
          glowSpot.style.transform = `translate(${mouseX - 125}px, ${mouseY - 125}px)`;
        }
      }

      function onMouseEnter() {
        bounds = card.getBoundingClientRect();
        card.style.transition = 'transform 0.12s ease-out, box-shadow 0.2s ease';
      }

      function onMouseLeave() {
        card.style.transition = 'transform 0.45s ease, box-shadow 0.45s ease';
        card.style.transform = 'perspective(1000px) rotateX(0deg) rotateY(0deg) translateY(0)';

        const glowSpot = card.querySelector('.card-glow-spot');
        if (glowSpot) {
          glowSpot.style.opacity = '0';
        }
      }

      card.addEventListener('mouseenter', onMouseEnter);
      card.addEventListener('mousemove', rotateToMouse);
      card.addEventListener('mouseleave', onMouseLeave);
    });
  }

  // --- Live Clock for HUD ---
  function initLiveClock() {
    const clockEl = document.getElementById('live-hud-clock');
    if (!clockEl) return;

    function updateTime() {
      const now = new Date();
      const hours = String(now.getHours()).padStart(2, '0');
      const minutes = String(now.getMinutes()).padStart(2, '0');
      const seconds = String(now.getSeconds()).padStart(2, '0');
      clockEl.textContent = `${hours}:${minutes}:${seconds}`;
    }

    updateTime();
    setInterval(updateTime, 1000);
  }

  // --- Initialize on load ---
  function initAll() {
    loadThreeJs(function () {
      initThreeScene();
    });
    initCardTilt();
    initLiveClock();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAll);
  } else {
    initAll();
  }

})();
