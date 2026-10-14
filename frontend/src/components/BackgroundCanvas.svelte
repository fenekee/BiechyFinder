<script>
  import { onMount, onDestroy } from 'svelte';
  import gsap from 'gsap';

  // Props
  export let appState = 'idle'; // 'idle' | 'scanning' | 'ai_thinking'

  let canvas;
  let ctx;
  let animationFrameId;
  let width = 0;
  let height = 0;

  // Configuration de la grille
  const SPACING = 28;
  const BASE_RADIUS = 1.2;
  const MOUSE_RADIUS = 140;

  // Souris lissée par GSAP quickTo
  const mouse = { x: -1000, y: -1000, radius: 0 };
  let quickX;
  let quickY;
  let quickPulse;

  // Variables d'onde selon appState
  let waveProgress = { value: 0 };
  let pulseIntensity = { value: 0 };
  let waveTween = null;
  let pulseTween = null;

  // Palette réactive selon appState
  $: themeColors = getColorsForState(appState);

  function getColorsForState(state) {
    if (state === 'scanning') {
      return {
        dotBase: 'rgba(56, 189, 248, 0.18)',     // Cyan / Sky
        dotActive: 'rgba(56, 189, 248, 0.85)',
        halo: 'rgba(14, 165, 233, 0.12)'
      };
    } else if (state === 'ai_thinking') {
      return {
        dotBase: 'rgba(192, 132, 252, 0.22)',    // Violet / Amethyst
        dotActive: 'rgba(216, 180, 254, 0.9)',
        halo: 'rgba(168, 85, 247, 0.15)'
      };
    }
    // Idle
    return {
      dotBase: 'rgba(255, 255, 255, 0.12)',      // Zinc neutre
      dotActive: 'rgba(129, 140, 248, 0.75)',    // Indigo doux
      halo: 'rgba(99, 102, 241, 0.08)'
    };
  }

  // Réagir aux changements de appState avec des animations GSAP
  $: if (canvas && appState) {
    handleStateChange(appState);
  }

  function handleStateChange(state) {
    if (waveTween) waveTween.kill();
    if (pulseTween) pulseTween.kill();

    if (state === 'scanning') {
      // Onde dynamique qui balaye l'écran
      waveProgress.value = 0;
      waveTween = gsap.to(waveProgress, {
        value: 1,
        duration: 2.2,
        repeat: -1,
        ease: 'power1.inOut'
      });
      pulseTween = gsap.to(pulseIntensity, {
        value: 1,
        duration: 0.8,
        yoyo: true,
        repeat: -1,
        ease: 'sine.inOut'
      });
    } else if (state === 'ai_thinking') {
      // Pulsation concentrique intense
      waveProgress.value = 0;
      waveTween = gsap.to(waveProgress, {
        value: 1,
        duration: 1.6,
        repeat: -1,
        ease: 'sine.out'
      });
      pulseTween = gsap.to(pulseIntensity, {
        value: 1.2,
        duration: 0.9,
        yoyo: true,
        repeat: -1,
        ease: 'power2.inOut'
      });
    } else {
      // Retour doux au repos
      waveTween = gsap.to(waveProgress, { value: 0, duration: 0.8 });
      pulseTween = gsap.to(pulseIntensity, { value: 0, duration: 0.8 });
    }
  }

  function resize() {
    if (!canvas) return;
    const dpr = window.devicePixelRatio || 1;
    width = window.innerWidth;
    height = window.innerHeight;
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;
    ctx = canvas.getContext('2d');
    ctx.scale(dpr, dpr);
  }

  function onMouseMove(e) {
    if (quickX && quickY) {
      quickX(e.clientX);
      quickY(e.clientY);
    }
  }

  function onMouseLeave() {
    if (quickX && quickY) {
      quickX(-1000);
      quickY(-1000);
    }
  }

  function draw() {
    if (!ctx) return;
    ctx.clearRect(0, 0, width, height);

    const mx = mouse.x;
    const my = mouse.y;
    const isScanning = appState === 'scanning';
    const isAi = appState === 'ai_thinking';

    // 1. Halo lumineux sous la souris
    if (mx > -500) {
      const gradient = ctx.createRadialGradient(mx, my, 0, mx, my, MOUSE_RADIUS * 1.5);
      gradient.addColorStop(0, themeColors.halo);
      gradient.addColorStop(1, 'rgba(0,0,0,0)');
      ctx.fillStyle = gradient;
      ctx.beginPath();
      ctx.arc(mx, my, MOUSE_RADIUS * 1.5, 0, Math.PI * 2);
      ctx.fill();
    }

    // 2. Tracé de la grille de points
    const cols = Math.ceil(width / SPACING) + 1;
    const rows = Math.ceil(height / SPACING) + 1;
    const maxDistDiag = Math.sqrt(width * width + height * height);

    for (let i = 0; i < cols; i++) {
      const px = i * SPACING;
      for (let j = 0; j < rows; j++) {
        const py = j * SPACING;

        // Interaction souris : calcul du décalage (écartement) et de l'intensité
        let dx = px - mx;
        let dy = py - my;
        let dist = Math.sqrt(dx * dx + dy * dy);
        let offsetX = 0;
        let offsetY = 0;
        let scale = 1;
        let alpha = 0.15;

        if (dist < MOUSE_RADIUS) {
          const factor = (1 - dist / MOUSE_RADIUS);
          const push = factor * 9; // Léger écartement élastique des points
          offsetX = (dx / (dist || 1)) * push;
          offsetY = (dy / (dist || 1)) * push;
          scale = 1 + factor * 1.4;
          alpha = 0.15 + factor * 0.7;
        }

        // Effet d'onde de scan ou IA
        if (isScanning) {
          // Onde diagonale qui traverse l'écran
          const waveX = (px + py) / (width + height);
          const waveDiff = Math.abs(waveX - waveProgress.value);
          if (waveDiff < 0.12) {
            const waveBoost = (1 - waveDiff / 0.12) * pulseIntensity.value;
            scale += waveBoost * 1.2;
            alpha = Math.max(alpha, waveBoost * 0.85);
          }
        } else if (isAi) {
          // Onde concentrique circulaire depuis le centre
          const cx = width / 2;
          const cy = height / 2;
          const distCenter = Math.sqrt((px - cx) * (px - cx) + (py - cy) * (py - cy));
          const normDist = distCenter / (maxDistDiag * 0.6);
          const waveDiff = Math.abs(normDist - waveProgress.value);
          if (waveDiff < 0.1) {
            const waveBoost = (1 - waveDiff / 0.1) * pulseIntensity.value;
            scale += waveBoost * 1.5;
            alpha = Math.max(alpha, waveBoost * 0.95);
          }
        }

        // Dessin du point
        ctx.fillStyle = alpha > 0.4 ? themeColors.dotActive : themeColors.dotBase;
        ctx.beginPath();
        ctx.arc(px + offsetX, py + offsetY, BASE_RADIUS * scale, 0, Math.PI * 2);
        ctx.fill();
      }
    }

    animationFrameId = requestAnimationFrame(draw);
  }

  onMount(() => {
    resize();
    window.addEventListener('resize', resize);
    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('mouseleave', onMouseLeave);

    // Initialisation GSAP quickTo pour réactivité souris 120Hz/144Hz sans latence
    quickX = gsap.quickTo(mouse, 'x', { duration: 0.35, ease: 'power2.out' });
    quickY = gsap.quickTo(mouse, 'y', { duration: 0.35, ease: 'power2.out' });

    animationFrameId = requestAnimationFrame(draw);
  });

  onDestroy(() => {
    if (animationFrameId) cancelAnimationFrame(animationFrameId);
    if (waveTween) waveTween.kill();
    if (pulseTween) pulseTween.kill();
    window.removeEventListener('resize', resize);
    window.removeEventListener('mousemove', onMouseMove);
    window.removeEventListener('mouseleave', onMouseLeave);
  });
</script>

<canvas
  bind:this={canvas}
  class="fixed inset-0 -z-10 pointer-events-none"
></canvas>
