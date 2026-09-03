/**
 * Social AI Assistant - 3D WebGL Neural Scene & Interactive Effects
 * Matrix / Security Cyber Green Theme
 * Powered by Three.js
 */

(function () {
  'use strict';

  // --- Three.js 3D Neural Scene ---
  let scene, camera, renderer;
  let particlesGroup, neuralSphereGroup, orbitRingGroup;
  let mouseX = 0, mouseY = 0;
  let targetX = 0, targetY = 0;
  const windowHalfX = window.innerWidth / 2;
  const windowHalfY = window.innerHeight / 2;

  function initThreeScene() {
    const container = document.getElementById('canvas-container');
    if (!container || typeof THREE === 'undefined') {
      console.warn('Three.js or canvas container not found, skipping 3D initialization.');
      return;
    }

    // 1. Create Scene & Camera
    scene = new THREE.Scene();
    camera = new THREE.PerspectiveCamera(55, window.innerWidth / window.innerHeight, 1, 2000);
    camera.position.z = 850;

    // 2. Create Renderer
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    } catch (e) {
      console.warn('WebGL not supported:', e);
      return;
    }

    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    container.appendChild(renderer.domElement);

    // 3. Create Ambient Floating Cyber Green & Gold Nebula Particles
    const particleCount = 750;
    const particleGeometry = new THREE.BufferGeometry();
    const positions = new Float32Array(particleCount * 3);
    const colors = new Float32Array(particleCount * 3);

    const colorGreenPrimary = new THREE.Color(0x00e676); // Neon Matrix Green
    const colorGreenDeep = new THREE.Color(0x00a152);    // Police Dark Green
    const colorGold = new THREE.Color(0xf59e0b);         // Emblem Gold Accent

    for (let i = 0; i < particleCount; i++) {
      positions[i * 3] = (Math.random() - 0.5) * 1600;
      positions[i * 3 + 1] = (Math.random() - 0.5) * 1200;
      positions[i * 3 + 2] = (Math.random() - 0.5) * 1200;

      const mixedColor = i % 4 === 0 ? colorGold : (i % 2 === 0 ? colorGreenPrimary : colorGreenDeep);
      colors[i * 3] = mixedColor.r;
      colors[i * 3 + 1] = mixedColor.g;
      colors[i * 3 + 2] = mixedColor.b;
    }

    particleGeometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    particleGeometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));

    // Particle material
    const particleMaterial = new THREE.PointsMaterial({
      size: 4,
      vertexColors: true,
      transparent: true,
      opacity: 0.7,
      blending: THREE.AdditiveBlending
    });

    particlesGroup = new THREE.Points(particleGeometry, particleMaterial);
    scene.add(particlesGroup);

    // 4. Create Interactive Security & AI Neural Sphere
    neuralSphereGroup = new THREE.Group();

    // Core Icosahedron Wireframe (Cyber Green)
    const icoGeo = new THREE.IcosahedronGeometry(220, 2);
    const icoMat = new THREE.MeshBasicMaterial({
      color: 0x00e676,
      wireframe: true,
      transparent: true,
      opacity: 0.3
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

    // Inner Glowing Core Sphere (Deep Green)
    const innerGeo = new THREE.SphereGeometry(140, 24, 24);
    const innerMat = new THREE.MeshBasicMaterial({
      color: 0x00a152,
      wireframe: true,
      transparent: true,
      opacity: 0.2
    });
    const innerMesh = new THREE.Mesh(innerGeo, innerMat);
    neuralSphereGroup.add(innerMesh);

    // Position sphere to the right on desktop, center on mobile
    if (window.innerWidth > 992) {
      neuralSphereGroup.position.set(280, 0, -50);
    } else {
      neuralSphereGroup.position.set(0, -60, -100);
      neuralSphereGroup.scale.set(0.75, 0.75, 0.75);
    }

    scene.add(neuralSphereGroup);

    // 5. Orbiting Data Rings (Green & Golden Ring)
    orbitRingGroup = new THREE.Group();
    const ringGeo1 = new THREE.RingGeometry(320, 322, 64);
    const ringMat1 = new THREE.MeshBasicMaterial({
      color: 0x00e676,
      side: THREE.DoubleSide,
      transparent: true,
      opacity: 0.4
    });
    const ringMesh1 = new THREE.Mesh(ringGeo1, ringMat1);
    ringMesh1.rotation.x = Math.PI / 3;
    ringMesh1.rotation.y = Math.PI / 6;
    orbitRingGroup.add(ringMesh1);

    const ringGeo2 = new THREE.RingGeometry(360, 362, 64);
    const ringMat2 = new THREE.MeshBasicMaterial({
      color: 0xf59e0b, // Golden Ring
      side: THREE.DoubleSide,
      transparent: true,
      opacity: 0.3
    });
    const ringMesh2 = new THREE.Mesh(ringGeo2, ringMat2);
    ringMesh2.rotation.x = -Math.PI / 4;
    ringMesh2.rotation.y = Math.PI / 3;
    orbitRingGroup.add(ringMesh2);

    neuralSphereGroup.add(orbitRingGroup);

    // 6. Listeners
    window.addEventListener('resize', onWindowResize, false);
    document.addEventListener('mousemove', onDocumentMouseMove, false);
    document.addEventListener('touchmove', onDocumentTouchMove, { passive: true });

    // 7. Start Animation Loop
    animate();
  }

  function onWindowResize() {
    if (!camera || !renderer) return;
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);

    if (neuralSphereGroup) {
      if (window.innerWidth > 992) {
        neuralSphereGroup.position.set(280, 0, -50);
        neuralSphereGroup.scale.set(1, 1, 1);
      } else {
        neuralSphereGroup.position.set(0, -60, -100);
        neuralSphereGroup.scale.set(0.75, 0.75, 0.75);
      }
    }
  }

  function onDocumentMouseMove(event) {
    mouseX = (event.clientX - windowHalfX) * 0.4;
    mouseY = (event.clientY - windowHalfY) * 0.4;
  }

  function onDocumentTouchMove(event) {
    if (event.touches.length > 0) {
      mouseX = (event.touches[0].clientX - windowHalfX) * 0.3;
      mouseY = (event.touches[0].clientY - windowHalfY) * 0.3;
    }
  }

  function animate() {
    requestAnimationFrame(animate);

    // Smooth camera / target parallax lerp
    targetX += (mouseX - targetX) * 0.05;
    targetY += (mouseY - targetY) * 0.05;

    camera.position.x = targetX * 0.3;
    camera.position.y = -targetY * 0.3;
    camera.lookAt(scene.position);

    // Continuous 3D rotations
    if (neuralSphereGroup) {
      neuralSphereGroup.rotation.y += 0.004;
      neuralSphereGroup.rotation.x += 0.002;
    }

    if (orbitRingGroup) {
      orbitRingGroup.rotation.z -= 0.006;
      orbitRingGroup.rotation.x += 0.003;
    }

    if (particlesGroup) {
      particlesGroup.rotation.y += 0.0008;
      particlesGroup.rotation.x += 0.0004;
    }

    renderer.render(scene, camera);
  }

  // --- 3D Card Tilt Interaction ---
  function initTiltCards() {
    const cards = document.querySelectorAll('.tilt-card');
    cards.forEach(card => {
      card.addEventListener('mousemove', e => {
        const rect = card.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;

        card.style.setProperty('--mouse-x', `${x}px`);
        card.style.setProperty('--mouse-y', `${y}px`);

        const centerX = rect.width / 2;
        const centerY = rect.height / 2;
        const rotateX = ((y - centerY) / centerY) * -10;
        const rotateY = ((x - centerX) / centerX) * 10;

        card.style.transform = `perspective(1000px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) translateY(-6px)`;
      });

      card.addEventListener('mouseleave', () => {
        card.style.transform = 'perspective(1000px) rotateX(0deg) rotateY(0deg) translateY(0)';
      });
    });
  }

  // --- Live Latency & Status Simulation ---
  function initStatusHUD() {
    const latencyEl = document.getElementById('hud-latency');
    if (!latencyEl) return;

    setInterval(() => {
      const randomLatency = Math.floor(Math.random() * 12) + 12;
      latencyEl.innerHTML = `${randomLatency} <small>ms</small>`;
    }, 3000);
  }

  // --- Initialize when DOM is ready ---
  document.addEventListener('DOMContentLoaded', () => {
    initThreeScene();
    initTiltCards();
    initStatusHUD();
  });
})();
