/* ══════════════════════════════════════════════════════════════════════════
   Sagoma 3D del DarkPaw — Three.js, senza build.

   Il modello è costruito con le proporzioni del ragno vero (piastre in
   acrilico, quattro zampe a tre segmenti, servi in vista) e viene animato
   leggendo /api/posa, cioè i PWM realmente scritti sul PCA9685.

   La quota del corpo non è finta: si calcola dalla cinematica delle zampe.
   Il piede più basso resta a terra, quindi se tutti i servi "piegano" le
   zampe il corpo si abbassa, esattamente come il robot vero.
   ══════════════════════════════════════════════════════════════════════════ */
import * as THREE from './three.module.min.js';

const host = document.getElementById('avatar-ragno');
if (host) {
  const tela = host.querySelector('canvas');
  if (tela) {
    try {
      avvia(tela);
    } catch (errore) {
      host.classList.add('senza3d');
      console.warn('ragno3d:', errore);
    }
  }
}

function avvia(tela) {
  const D = Math.PI / 180;

  /* ── quote del ragno (unità del modello) ───────────────────────────────── */
  const NEUTRO = 300;
  const HIP_Y = 4.45;        // quota dell'asse di imbardata
  const L1 = 7.0;            // femore
  const PHI0 = 35;           // femore a riposo, gradi sopra l'orizzontale
  const PSI0 = -81;          // tibia a riposo, gradi rispetto al femore
  const CONTATTO_X = 11.375; // punta del piede nel sistema della tibia
  const CONTATTO_Y = -2.06;
  const CORPO_Y = 3.55;      // centro di rotazione per pitch e roll

  /* direzioni dei servi, come in SpiderG.py */
  const ZAMPE = [
    { id: 'FL', b: 'FLB', m: 'FLM', e: 'FLE', db: +1, dm: -1, de: -1, x: +4.15, z: +2.95, yaw: -35 },
    { id: 'FR', b: 'FRB', m: 'FRM', e: 'FRE', db: -1, dm: +1, de: +1, x: -4.15, z: +2.95, yaw: -145 },
    { id: 'HL', b: 'HLB', m: 'HLM', e: 'HLE', db: -1, dm: +1, de: +1, x: +4.15, z: -2.95, yaw: +35 },
    { id: 'HR', b: 'HRB', m: 'HRM', e: 'HRE', db: +1, dm: -1, de: -1, x: -4.15, z: -2.95, yaw: +145 }
  ];

  /* ── renderer, scena, camera ───────────────────────────────────────────── */
  const renderer = new THREE.WebGLRenderer({
    canvas: tela, alpha: true, antialias: true, powerPreference: 'high-performance'
  });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.48;
  renderer.setClearAlpha(0);

  const scena = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(24, 1.9, 0.5, 200);

  /* ── ambiente: riflessi caldi/freddi da studio ─────────────────────────── */
  const ambiente = creaAmbiente(renderer);
  scena.environment = ambiente;

  scena.add(new THREE.HemisphereLight(0x9db7ff, 0x2a1c14, 1.02));

  const chiave = new THREE.DirectionalLight(0xf4f8ff, 4.25);
  chiave.position.set(-14, 20, 16);
  scena.add(chiave);

  const controluce = new THREE.DirectionalLight(0x5fd2ff, 3.6);
  controluce.position.set(15, 12, -16);
  scena.add(controluce);

  const caldo = new THREE.DirectionalLight(0xff6a2a, 1.05);
  caldo.position.set(18, 5, 10);
  scena.add(caldo);

  const lato = new THREE.DirectionalLight(0xc7d4ff, 0.85);
  lato.position.set(-16, 8, -6);
  scena.add(lato);

  const frontale = new THREE.DirectionalLight(0xc6dcff, 1.55);
  frontale.position.set(2, 7, 20);
  scena.add(frontale);

  /* ── materiali ─────────────────────────────────────────────────────────── */
  const acrilico = new THREE.MeshPhysicalMaterial({
    color: 0x0e1016, metalness: 0.45, roughness: 0.13,
    clearcoat: 1, clearcoatRoughness: 0.05, envMapIntensity: 2.6
  });
  const acrilicoChiaro = new THREE.MeshPhysicalMaterial({
    color: 0x14171d, metalness: 0.40, roughness: 0.18,
    clearcoat: 0.9, clearcoatRoughness: 0.10, envMapIntensity: 1.8
  });
  const alluminio = new THREE.MeshStandardMaterial({
    color: 0xc9d2dc, metalness: 1.0, roughness: 0.24, envMapIntensity: 1.7
  });
  const servoScuro = new THREE.MeshStandardMaterial({
    color: 0x0b0c10, metalness: 0.35, roughness: 0.52, envMapIntensity: 0.9
  });
  const servoTop = new THREE.MeshStandardMaterial({
    color: 0x22252d, metalness: 0.5, roughness: 0.38, envMapIntensity: 1.1
  });
  const corno = new THREE.MeshStandardMaterial({
    color: 0xff8a4c, emissive: 0xff4a10, emissiveIntensity: 0.28,
    metalness: 0.2, roughness: 0.36
  });
  const etichetta = new THREE.MeshStandardMaterial({
    color: 0xcf2f5e, emissive: 0x7a0f2c, emissiveIntensity: 0.35,
    metalness: 0.1, roughness: 0.45
  });
  const pcbVerde = new THREE.MeshStandardMaterial({
    color: 0x1e7a48, metalness: 0.15, roughness: 0.50, envMapIntensity: 0.8
  });
  const pcbVerdeScuro = new THREE.MeshStandardMaterial({
    color: 0x0d3722, metalness: 0.25, roughness: 0.40, envMapIntensity: 1.0
  });
  const pcbBlu = new THREE.MeshStandardMaterial({
    color: 0x15345f, metalness: 0.35, roughness: 0.36, envMapIntensity: 1.2
  });
  const chip = new THREE.MeshStandardMaterial({
    color: 0x08090b, metalness: 0.4, roughness: 0.42
  });
  const oro = new THREE.MeshStandardMaterial({
    color: 0xd8a84a, metalness: 1.0, roughness: 0.28, envMapIntensity: 1.5
  });
  const piede = new THREE.MeshStandardMaterial({
    color: 0xd7d2c6, metalness: 0.05, roughness: 0.48, envMapIntensity: 0.9
  });
  const gomma = new THREE.MeshStandardMaterial({
    color: 0x101010, metalness: 0.1, roughness: 0.85
  });
  const lente = new THREE.MeshPhysicalMaterial({
    color: 0x05080d, metalness: 0.9, roughness: 0.06,
    clearcoat: 1, clearcoatRoughness: 0.03, envMapIntensity: 2.2
  });
  const vetro = new THREE.MeshPhysicalMaterial({
    color: 0x2a6f9e, metalness: 0.6, roughness: 0.08,
    transparent: true, opacity: 0.75, envMapIntensity: 2.2
  });
  const ledCiano = new THREE.MeshStandardMaterial({
    color: 0x0a2a2a, emissive: 0x53ffe0, emissiveIntensity: 2.0, roughness: 0.3
  });
  const ledRosso = new THREE.MeshStandardMaterial({
    color: 0x2a0808, emissive: 0xff2f2f, emissiveIntensity: 1.6, roughness: 0.3
  });
  const filoArancio = new THREE.MeshStandardMaterial({
    color: 0xff6a26, roughness: 0.55, metalness: 0.1
  });
  const filoNero = new THREE.MeshStandardMaterial({
    color: 0x141414, roughness: 0.7, metalness: 0.1
  });

  /* ── rig: scena → rig (quota) → inclinazione → scocca ─────────────────── */
  const scenaRagno = new THREE.Group();
  scena.add(scenaRagno);

  const rig = new THREE.Group();
  scenaRagno.add(rig);

  const inclina = new THREE.Group();
  inclina.position.y = CORPO_Y;
  rig.add(inclina);

  const scocca = new THREE.Group();
  scocca.position.y = -CORPO_Y;
  inclina.add(scocca);

  /* ══════════════════════ scocca ══════════════════════ */
  const piastraBassa = placca(arrotondato(11.0, 8.8, 1.45), 0.26);
  const corpoBasso = meshConBordi(piastraBassa, acrilico, 0xffd0a6, 0.17);
  corpoBasso.rotation.x = Math.PI / 2;
  corpoBasso.position.y = 1.30;
  scocca.add(corpoBasso);

  const formaAlta = arrotondato(10.4, 8.2, 1.30);
  formaAlta.holes.push(foroArrotondato(0, 0.25, 6.4, 3.9, 0.55));
  formaAlta.holes.push(foroArrotondato(4.30, 0.35, 1.15, 4.7, 0.30));
  formaAlta.holes.push(foroCircolo(-3.95, 0.0, 0.42));
  formaAlta.holes.push(foroCircolo(3.95, 0.0, 0.42));
  const piastraAlta = placca(formaAlta, 0.26);
  const corpoAlto = meshConBordi(piastraAlta, acrilico, 0xcfe0ff, 0.30);
  corpoAlto.rotation.x = Math.PI / 2;
  corpoAlto.position.y = 3.25;
  scocca.add(corpoAlto);

  /* colonnine */
  for (const [cx, cz] of [[-4.55, -3.35], [4.55, -3.35], [-4.55, 3.35], [4.55, 3.35], [-2.9, 0], [2.9, 0]]) {
    const colonna = new THREE.Mesh(new THREE.CylinderGeometry(0.13, 0.13, 1.72, 10), alluminio);
    colonna.position.set(cx, 2.30, cz);
    scocca.add(colonna);
    for (const dy of [-0.86, 0.86]) {
      const dado = new THREE.Mesh(new THREE.CylinderGeometry(0.22, 0.22, 0.10, 10), alluminio);
      dado.position.set(cx, 2.30 + dy, cz);
      scocca.add(dado);
    }
  }

  /* Raspberry Pi */
  const piBoard = new THREE.Mesh(new THREE.BoxGeometry(8.4, 0.13, 5.6), pcbVerde);
  piBoard.position.set(0, 1.72, 0);
  scocca.add(piBoard);

  const portaAcciaio = new THREE.MeshStandardMaterial({ color: 0xaeb6c0, metalness: 1, roughness: 0.28 });
  function porta(z, w, h, prof) {
    const guscio = new THREE.Mesh(new THREE.BoxGeometry(prof, h, w), portaAcciaio);
    guscio.position.set(4.45 + prof / 2, 1.79 + h / 2, z);
    scocca.add(guscio);
    const buco = new THREE.Mesh(new THREE.BoxGeometry(0.06, h * 0.62, w * 0.82), chip);
    buco.position.set(4.45 + prof + 0.01, 1.79 + h / 2, z);
    scocca.add(buco);
  }
  porta(-1.85, 1.35, 0.72, 1.20);
  porta(-0.35, 1.35, 0.72, 1.20);
  porta(1.25, 1.55, 0.88, 1.35);
  porta(2.60, 0.95, 0.62, 1.05);

  const header = new THREE.Mesh(new THREE.BoxGeometry(0.30, 0.26, 4.9), chip);
  header.position.set(-3.62, 1.90, -0.2);
  scocca.add(header);
  const pino = new THREE.Mesh(new THREE.BoxGeometry(0.42, 0.06, 4.9), oro);
  pino.position.set(-3.62, 2.05, -0.2);
  scocca.add(pino);

  for (const [cx, cz, sx, sz] of [[0.4, -1.15, 1.7, 1.1], [2.4, -1.3, 0.9, 0.9], [-1.7, 1.4, 1.0, 0.7]]) {
    const c = new THREE.Mesh(new THREE.BoxGeometry(sx, 0.22, sz), chip);
    c.position.set(cx, 1.88, cz);
    scocca.add(c);
  }
  const sd = new THREE.Mesh(new THREE.BoxGeometry(0.9, 0.08, 0.45), alluminio);
  sd.position.set(-2.8, 1.79, 2.1);
  scocca.add(sd);

  /* HAT */
  const hat = new THREE.Mesh(new THREE.BoxGeometry(6.6, 0.14, 4.6), pcbBlu);
  hat.position.set(0, 2.62, 0.05);
  scocca.add(hat);

  const morsetto = new THREE.Mesh(new THREE.BoxGeometry(1.15, 0.42, 1.5), chip);
  morsetto.position.set(2.55, 2.86, 0.15);
  scocca.add(morsetto);
  const pinMorsetto = new THREE.Mesh(new THREE.BoxGeometry(0.9, 0.10, 1.22), oro);
  pinMorsetto.position.set(2.55, 3.08, 0.15);
  scocca.add(pinMorsetto);

  for (const [cx, cz] of [[-2.30, 1.45], [-1.05, 1.45], [0.75, 1.45]]) {
    const condensatore = new THREE.Mesh(new THREE.CylinderGeometry(0.22, 0.22, 0.55, 12), pcbBlu);
    condensatore.position.set(cx, 2.90, cz);
    scocca.add(condensatore);
    const tappo = new THREE.Mesh(new THREE.CylinderGeometry(0.23, 0.23, 0.05, 12), alluminio);
    tappo.position.set(cx, 3.19, cz);
    scocca.add(tappo);
  }
  const pca = new THREE.Mesh(new THREE.BoxGeometry(0.95, 0.16, 0.95), chip);
  pca.position.set(0.55, 2.74, 0.2);
  scocca.add(pca);
  const mpu = new THREE.Mesh(new THREE.BoxGeometry(0.55, 0.14, 0.55), chip);
  mpu.position.set(-1.0, 2.74, 1.45);
  scocca.add(mpu);

  const headerHat = new THREE.Mesh(new THREE.BoxGeometry(0.34, 0.30, 3.9), chip);
  headerHat.position.set(-2.55, 2.80, -0.35);
  scocca.add(headerHat);
  const pinHat = new THREE.Mesh(new THREE.BoxGeometry(0.46, 0.06, 3.9), oro);
  pinHat.position.set(-2.55, 2.98, -0.35);
  scocca.add(pinHat);

  const ledHat = new THREE.Mesh(new THREE.BoxGeometry(0.22, 0.10, 0.16), ledCiano);
  ledHat.position.set(1.75, 2.73, -1.55);
  scocca.add(ledHat);
  const ledPower = new THREE.Mesh(new THREE.BoxGeometry(0.14, 0.08, 0.12), ledRosso);
  ledPower.position.set(2.2, 2.73, -1.55);
  scocca.add(ledPower);

  /* viti a vista della piastra superiore */
  for (const [sx, sz] of [[-4.9, -3.75], [4.9, -3.75], [-4.9, 3.75], [4.9, 3.75],
                           [-2.35, 2.55], [2.35, 2.55], [-2.35, -2.05], [2.35, -2.05]]) {
    const testa = new THREE.Mesh(new THREE.CylinderGeometry(0.16, 0.16, 0.07, 12), alluminio);
    testa.position.set(sx, 3.41, sz);
    scocca.add(testa);
    const taglio = new THREE.Mesh(new THREE.BoxGeometry(0.20, 0.025, 0.035), chip);
    taglio.position.set(sx, 3.46, sz);
    scocca.add(taglio);
  }

  /* telecamera frontale */
  const staffa = new THREE.Mesh(new THREE.BoxGeometry(1.9, 1.45, 0.38), acrilicoChiaro);
  staffa.position.set(0, 3.57, 4.08);
  scocca.add(staffa);
  const camPCB = new THREE.Mesh(new THREE.BoxGeometry(2.0, 1.8, 0.14), pcbVerdeScuro);
  camPCB.position.set(0, 3.57, 4.30);
  scocca.add(camPCB);
  const barilotto = new THREE.Mesh(new THREE.CylinderGeometry(0.70, 0.76, 0.78, 24), lente);
  barilotto.rotation.x = Math.PI / 2;
  barilotto.position.set(0, 3.57, 4.74);
  scocca.add(barilotto);
  const paraluce = new THREE.Mesh(new THREE.CylinderGeometry(0.86, 0.92, 0.24, 24), servoScuro);
  paraluce.rotation.x = Math.PI / 2;
  paraluce.position.set(0, 3.57, 5.02);
  scocca.add(paraluce);
  const ghiera = new THREE.Mesh(new THREE.TorusGeometry(0.66, 0.10, 10, 30), alluminio);
  ghiera.position.set(0, 3.57, 5.14);
  scocca.add(ghiera);
  const lenteVetro = new THREE.Mesh(new THREE.CircleGeometry(0.56, 28), vetro);
  lenteVetro.position.set(0, 3.57, 5.15);
  scocca.add(lenteVetro);
  const iride = new THREE.Mesh(new THREE.CircleGeometry(0.20, 20), ledCiano);
  iride.position.set(0, 3.57, 5.17);
  scocca.add(iride);
  const anello = new THREE.Mesh(new THREE.TorusGeometry(0.46, 0.035, 8, 28), ledCiano);
  anello.position.set(0, 3.57, 5.18);
  scocca.add(anello);
  const flash = spriteLuce(0x9fe8ff, 2.0);
  flash.position.set(0.26, 3.76, 5.22);
  scocca.add(flash);

  const filoGrigio = new THREE.MeshStandardMaterial({
    color: 0x8b919c, metalness: 0.2, roughness: 0.6
  });
  tavolaCavo([[0.62, 3.35, 4.40], [1.0, 3.28, 4.10], [1.15, 2.95, 3.60], [0.35, 2.78, 3.05]],
             filoGrigio, 0.095, scocca);
  tavolaCavo([[0.30, 3.30, 4.40], [0.65, 3.23, 4.10], [0.75, 2.92, 3.60], [0.05, 2.76, 3.05]],
             filoNero, 0.045, scocca);

  /* dissipatore sulla HAT */
  const dissipatore = new THREE.Mesh(new THREE.BoxGeometry(1.55, 0.28, 1.05), servoTop);
  dissipatore.position.set(1.15, 2.82, 0.55);
  scocca.add(dissipatore);
  for (let i = 0; i < 5; i++) {
    const aletta = new THREE.Mesh(new THREE.BoxGeometry(0.08, 0.16, 1.0), alluminio);
    aletta.position.set(0.55 + i * 0.30, 2.99, 0.55);
    scocca.add(aletta);
  }

  /* servi di base + staffe, fissi sulla scocca */
  for (const z of ZAMPE) {
    const base = new THREE.Group();
    base.position.set(z.x, 0, z.z);
    base.rotation.y = z.yaw * D;
    scocca.add(base);

    const staffaBase = new THREE.Mesh(new THREE.BoxGeometry(1.85, 0.24, 1.55), acrilicoChiaro);
    staffaBase.position.set(0.55, 3.40, 0);
    base.add(staffaBase);

    const scatola = new THREE.Mesh(new THREE.BoxGeometry(1.25, 1.30, 1.25), servoScuro);
    scatola.position.set(0.55, 3.95, 0);
    base.add(scatola);
    const coperchio = new THREE.Mesh(new THREE.BoxGeometry(1.15, 0.12, 1.15), servoTop);
    coperchio.position.set(0.55, 4.62, 0);
    base.add(coperchio);
    const etichettaBase = new THREE.Mesh(new THREE.BoxGeometry(0.72, 0.03, 0.50), etichetta);
    etichettaBase.position.set(0.55, 4.69, 0);
    base.add(etichettaBase);
  }

  /* fasci di cavi sulla scocca */
  const curvaCavi = [
    [[2.6, 2.90, 1.0], [4.2, 3.95, 2.2], [4.55, 4.28, 2.95]],
    [[2.6, 2.90, -0.5], [4.4, 3.75, -1.4], [4.55, 4.28, -2.95]],
    [[-2.6, 2.70, 0.5], [-4.3, 3.25, 1.4], [-4.55, 3.85, 2.9]],
    [[-2.6, 2.70, -0.5], [-4.3, 3.2, -1.5], [-4.55, 3.85, -2.9]]
  ];
  for (const [i, punti] of curvaCavi.entries()) {
    tavolaCavo(punti, i % 2 ? filoNero : filoArancio, i < 2 ? 0.085 : 0.06, scocca);
    if (i < 2) tavolaCavo(punti.map(p => [p[0], p[1] - 0.12, p[2] + 0.12]), filoNero, 0.045, scocca);
  }

  /* ══════════════════════ zampe ══════════════════════ */
  const gambe = ZAMPE.map(creaGamba);

  function creaGamba(def) {
    const root = new THREE.Group();
    root.position.set(def.x, HIP_Y, def.z);
    root.rotation.y = def.yaw * D;
    scocca.add(root);

    /* mozzo che ruota con la zampa */
    const mozzo = new THREE.Mesh(new THREE.CylinderGeometry(0.56, 0.60, 0.26, 16), acrilicoChiaro);
    mozzo.position.y = 0.02;
    root.add(mozzo);
    const cornoBase = new THREE.Mesh(new THREE.CylinderGeometry(0.42, 0.42, 0.12, 16), corno);
    cornoBase.position.y = 0.18;
    root.add(cornoBase);
    for (let i = 0; i < 4; i++) {
      const raggio = new THREE.Mesh(new THREE.BoxGeometry(0.64, 0.10, 0.13), corno);
      raggio.rotation.y = i * Math.PI / 2;
      raggio.position.y = 0.20;
      root.add(raggio);
    }

    const femore = new THREE.Group();
    root.add(femore);

    const perno = new THREE.Mesh(new THREE.CylinderGeometry(0.38, 0.38, 1.22, 14), alluminio);
    perno.rotation.x = Math.PI / 2;
    femore.add(perno);

    for (const dz of [-0.52, 0.52]) {
      const lastra = meshConBordi(placca(formaFemore(), 0.22), acrilico, 0xffd0a6, 0.19);
      lastra.position.z = dz;
      lastra.scale.y = 1.32;
      femore.add(lastra);
    }

    vite(femore, 0.35, 0.0, 0.62);
    vite(femore, 4.55, 0.10, 0.62);
    vite(femore, 4.55, 0.10, 0.62, 0.55);
    vite(femore, 6.75, 0.02, 0.62);

    const servoM = gruppoServo(1.15, 0.86, 0, 0.62);
    femore.add(servoM);

    const cavoM = tavolaCavo([[1.5, 1.12, 0.42], [0.9, 0.55, 0.95], [0.25, 0.15, 0.9]], filoArancio, 0.048, femore);

    const tibia = new THREE.Group();
    tibia.position.x = L1;
    femore.add(tibia);

    const ginocchio = new THREE.Mesh(new THREE.CylinderGeometry(0.36, 0.36, 1.08, 14), alluminio);
    ginocchio.rotation.x = Math.PI / 2;
    tibia.add(ginocchio);

    for (const dz of [-0.48, 0.48]) {
      const lastra = meshConBordi(placca(formaTibia(), 0.24), acrilico, 0xffd0a6, 0.19);
      lastra.position.z = dz;
      lastra.scale.y = 1.26;
      tibia.add(lastra);
    }

    for (let i = 0; i < 6; i++) vite(tibia, 1.0 + i * 1.25, 0.0, 0.58); 
    vite(tibia, 8.9, 0.02, 0.58);

    const servoE = gruppoServo(1.10, 0.86, 0, 0.58);
    tibia.add(servoE);

    const cavoE = tavolaCavo([[1.45, 1.10, 0.4], [2.5, 0.6, 0.95], [1.0, 0.2, 0.9]], filoNero, 0.045, tibia);

    const piedeGruppo = new THREE.Group();
    piedeGruppo.position.x = 9.5;
    tibia.add(piedeGruppo);

    const formaPiede = formaPiede3D();
    const piedeMesh = meshConBordi(placca(formaPiede, 0.62, 0.06), piede, 0xffd7b0, 0.16);
    piedeMesh.scale.set(1.25, 1.25, 1.12);
    piedeGruppo.add(piedeMesh);

    const gommino = new THREE.Mesh(new THREE.BoxGeometry(0.55, 0.20, 0.72), gomma);
    gommino.position.set(1.78, -2.02, 0);
    gommino.rotation.z = -0.18;
    piedeGruppo.add(gommino);

    /* punta arrotondata: si vede anche quando il piede è di taglio */
    const punta = new THREE.Mesh(new THREE.CapsuleGeometry(0.33, 0.34, 4, 10), piede);
    punta.rotation.x = Math.PI / 2;
    punta.position.set(1.70, -1.72, 0);
    piedeGruppo.add(punta);

    /* punto di contatto, serve per l'ombra e per la quota */
    const contatto = new THREE.Object3D();
    contatto.position.set(1.875, -2.06, 0);
    piedeGruppo.add(contatto);

    return { def, root, femore, tibia, servoM, servoE, piede: piedeGruppo, contatto, cavoM, cavoE };
  }

  /* ══════════════════════ ombre ══════════════════════ */
  const ombraTerra = new THREE.Mesh(
    new THREE.PlaneGeometry(24, 18),
    new THREE.MeshBasicMaterial({
      map: textureOmbra(), transparent: true, opacity: 0.78,
      depthWrite: false, color: 0x000000
    })
  );
  ombraTerra.rotation.x = -Math.PI / 2;
  ombraTerra.position.y = 0.008;
  scena.add(ombraTerra);

  const ombrePiedi = ZAMPE.map(() => {
    const m = new THREE.Mesh(
      new THREE.PlaneGeometry(3.0, 3.0),
      new THREE.MeshBasicMaterial({
        map: textureOmbra(), transparent: true, opacity: 0.4,
        depthWrite: false, color: 0x000000
      })
    );
    m.rotation.x = -Math.PI / 2;
    m.position.y = 0.012;
    scena.add(m);
    return m;
  });

  /* ── scala e inquadratura ──────────────────────────────────────────────── */
  const box0 = new THREE.Box3().setFromObject(rig);
  const dim0 = box0.getSize(new THREE.Vector3());
  const scala = 23 / Math.max(dim0.x, dim0.z);
  scenaRagno.scale.setScalar(scala);

  const dirCamera = new THREE.Vector3(0.42, 0.60, 0.68).normalize();
  const bersaglioCamera = new THREE.Vector3(0, 3.00, 1.0);
  camera.position.copy(bersaglioCamera).addScaledVector(dirCamera, 33.5);
  camera.lookAt(bersaglioCamera);
  camera.updateProjectionMatrix();

  const luce = new THREE.PointLight(0x8fe8ff, 10, 22, 2);
  luce.position.set(0, 7, 8);
  scena.add(luce);

  const bagliore = new THREE.PointLight(0xff5a1e, 4.5, 8, 2);
  bagliore.position.set(0, 1.15, 1.2);
  scena.add(bagliore);

  /* ── stato e lettura dei servi ─────────────────────────────────────────── */
  const servo = {};
  const obiettivo = {};
  for (const z of ZAMPE) {
    for (const k of ['b', 'm', 'e']) {
      servo[z[k]] = NEUTRO;
      obiettivo[z[k]] = NEUTRO;
    }
  }
  const assetto = { pitch: 0, roll: 0 };
  const assettoObiettivo = { pitch: 0, roll: 0 };

  let primoDato = false;
  let inCorso = false;

  async function leggiPosa() {
    if (inCorso || document.hidden) return;
    inCorso = true;
    try {
      const ris = await fetch('/api/posa', { cache: 'no-store', credentials: 'same-origin' });
      if (!ris.ok) return;
      const dati = await ris.json();
      if (!dati || !dati.servi) return;
      for (const nome in dati.servi) {
        if (nome in obiettivo) obiettivo[nome] = Number(dati.servi[nome]) || NEUTRO;
      }
      assettoObiettivo.pitch = Number(dati.pitch) || 0;
      assettoObiettivo.roll = Number(dati.roll) || 0;
      if (!primoDato) {
        Object.assign(servo, obiettivo);
        Object.assign(assetto, assettoObiettivo);
        primoDato = true;
      }
    } catch (_) {
      /* la telecamera continua: la sagoma resta sull'ultima posa */
    } finally {
      inCorso = false;
    }
  }

  leggiPosa();
  const timer = window.setInterval(leggiPosa, 140);
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) leggiPosa();
  });

  /* ── aggiornamento cinematico ──────────────────────────────────────────── */
  let quota = null;
  let ultimo = performance.now();
  let tempo = 0;

  function aggiorna(dt, adesso) {
    const k = 1 - Math.exp(-dt * 10.5);
    for (const nome in servo) servo[nome] += (obiettivo[nome] - servo[nome]) * k;
    assetto.pitch += (assettoObiettivo.pitch - assetto.pitch) * k;
    assetto.roll += (assettoObiettivo.roll - assetto.roll) * k;

    let piedePiuBasso = Infinity;

    for (let i = 0; i < gambe.length; i++) {
      const g = gambe[i];
      const b = servo[g.def.b];
      const m = servo[g.def.m];
      const e = servo[g.def.e];

      /* positivo = zampa che si raccoglie (il servo "tira su") */
      const raccogli = (m - NEUTRO) * -g.def.dm;
      /* positivo = punta che si solleva */
      const arriccia = (e - NEUTRO) * g.def.de;

      let phi = (PHI0 + raccogli * 0.075) * D;
      let psi = (PSI0 + arriccia * 0.17) * D;
      phi = Math.max(0.10, Math.min(1.22, phi));
      psi = Math.max(-2.05, Math.min(-0.62, psi));

      const imbardata = (g.def.yaw + (b - NEUTRO) * g.def.db * 0.22) * D;
      g.root.rotation.y = imbardata;
      g.femore.rotation.z = phi;
      g.tibia.rotation.z = psi;

      const a = phi + psi;
      const fy = HIP_Y + L1 * Math.sin(phi) +
                 CONTATTO_X * Math.sin(a) + CONTATTO_Y * Math.cos(a);
      if (fy < piedePiuBasso) piedePiuBasso = fy;

      /* ombra sotto la punta: segue la posizione reale del piede */
      const fx = L1 * Math.cos(phi) +
                 CONTATTO_X * Math.cos(a) - CONTATTO_Y * Math.sin(a);
      const wx = g.def.x + fx * Math.cos(imbardata);
      const wz = g.def.z - fx * Math.sin(imbardata);
      const altezza = Math.max(0, fy + (quota ?? 0));
      const ombra = ombrePiedi[i];
      ombra.position.x = wx * scala;
      ombra.position.z = wz * scala;
      const s = (0.85 + altezza * 0.10) * scala;
      ombra.scale.set(s, s, 1);
      ombra.material.opacity = Math.max(0.05, 0.42 - altezza * 0.055);
    }

    if (quota === null) quota = -piedePiuBasso;
    else quota += (-piedePiuBasso - quota) * (1 - Math.exp(-dt * 13));
    rig.position.y = quota;

    inclina.rotation.x = -assetto.pitch * 0.42 * D;
    inclina.rotation.z = assetto.roll * 0.46 * D;

    /* respiro leggerissimo del gruppo led, per non farlo sembrare un fermo */
    tempo = adesso / 1000;
    const pulsazione = 0.75 + Math.sin(tempo * 2.1) * 0.25;
    ledCiano.emissiveIntensity = 1.4 + pulsazione * 1.2;
    ledRosso.emissiveIntensity = 1.15 + pulsazione * 0.8;
    flash.material.opacity = 0.20 + pulsazione * 0.22;
    flash.scale.setScalar(1.25 + pulsazione * 0.35);
  }

  function dimensiona() {
    const w = host.clientWidth;
    const h = host.clientHeight;
    if (!w || !h) return;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  }

  dimensiona();
  window.addEventListener('resize', dimensiona);
  if (window.ResizeObserver) new ResizeObserver(dimensiona).observe(host);

  /* ── ciclo ─────────────────────────────────────────────────────────────── */
  function frame(adesso) {
    requestAnimationFrame(frame);
    const dt = Math.min(0.05, (adesso - ultimo) / 1000);
    ultimo = adesso;
    if (document.hidden) return;
    aggiorna(dt, adesso);
    renderer.render(scena, camera);
  }
  requestAnimationFrame(frame);

  /* ══════════════════════ geometrie ══════════════════════ */

  function arrotondato(w, h, r) {
    const s = new THREE.Shape();
    const x = -w / 2, y = -h / 2;
    const rr = Math.min(r, w / 2, h / 2);
    s.moveTo(x + rr, y);
    s.lineTo(x + w - rr, y);
    s.quadraticCurveTo(x + w, y, x + w, y + rr);
    s.lineTo(x + w, y + h - rr);
    s.quadraticCurveTo(x + w, y + h, x + w - rr, y + h);
    s.lineTo(x + rr, y + h);
    s.quadraticCurveTo(x, y + h, x, y + h - rr);
    s.lineTo(x, y + rr);
    s.quadraticCurveTo(x, y, x + rr, y);
    return s;
  }

  function foroArrotondato(cx, cy, w, h, r) {
    const p = new THREE.Path();
    const x = cx - w / 2, y = cy - h / 2;
    const rr = Math.min(r, w / 2, h / 2);
    p.moveTo(x + rr, y);
    p.quadraticCurveTo(x, y, x, y + rr);
    p.lineTo(x, y + h - rr);
    p.quadraticCurveTo(x, y + h, x + rr, y + h);
    p.lineTo(x + w - rr, y + h);
    p.quadraticCurveTo(x + w, y + h, x + w, y + h - rr);
    p.lineTo(x + w, y + rr);
    p.quadraticCurveTo(x + w, y, x + w - rr, y);
    p.lineTo(x + rr, y);
    return p;
  }

  function foroCircolo(cx, cy, r) {
    const p = new THREE.Path();
    p.absarc(cx, cy, r, 0, Math.PI * 2, true);
    return p;
  }

  function foroTriangolo(punti, arco) {
    const p = new THREE.Path();
    p.moveTo(punti[0][0], punti[0][1]);
    for (let i = 1; i < punti.length; i++) {
      const a = punti[i - 1], b = punti[i];
      p.lineTo(b[0], b[1]);
      if (i === punti.length - 1) p.quadraticCurveTo(b[0] + arco, b[1] + arco, punti[0][0], punti[0][1]);
    }
    p.closePath();
    return p;
  }

  function placca(shape, spessore, bevel = 0.045) {
    const g = new THREE.ExtrudeGeometry(shape, {
      depth: spessore, bevelEnabled: true,
      bevelThickness: bevel, bevelSize: bevel, bevelSegments: 2,
      curveSegments: 12, steps: 1
    });
    g.translate(0, 0, -spessore / 2);
    return g;
  }

  function meshConBordi(geometria, materiale, coloreBordo, opacita) {
    const mesh = new THREE.Mesh(geometria, materiale);
    const bordi = new THREE.LineSegments(
      new THREE.EdgesGeometry(geometria, 34),
      new THREE.LineBasicMaterial({
        color: coloreBordo, transparent: true, opacity: opacita,
        depthWrite: false
      })
    );
    mesh.add(bordi);
    return mesh;
  }

  function formaFemore() {
    const s = new THREE.Shape();
    s.moveTo(0.32, 0.92);
    s.quadraticCurveTo(1.2, 1.14, 2.1, 1.10);
    s.lineTo(4.2, 0.92);
    s.quadraticCurveTo(5.5, 0.86, 6.55, 0.58);
    s.quadraticCurveTo(6.95, 0.44, 6.85, 0.05);
    s.lineTo(6.55, -0.48);
    s.lineTo(4.2, -0.78);
    s.quadraticCurveTo(2.0, -0.92, 0.62, -0.62);
    s.quadraticCurveTo(0.10, -0.35, 0.18, 0.35);
    s.quadraticCurveTo(0.20, 0.72, 0.32, 0.92);
    s.closePath();
    s.holes.push(foroCircolo(1.25, 0.10, 0.36));
    s.holes.push(foroTriangolo([[2.35, -0.42], [4.55, 0.34], [5.55, -0.35]], 0.10));
    s.holes.push(foroCircolo(6.05, 0.08, 0.30));
    return s;
  }

  function formaTibia() {
    const s = new THREE.Shape();
    s.moveTo(0.12, 0.74);
    s.quadraticCurveTo(1.6, 0.94, 3.1, 0.82);
    s.lineTo(6.4, 0.56);
    s.quadraticCurveTo(8.7, 0.42, 9.55, 0.18);
    s.quadraticCurveTo(9.85, 0.05, 9.72, -0.20);
    s.lineTo(9.35, -0.56);
    s.lineTo(6.1, -0.68);
    s.quadraticCurveTo(3.1, -0.76, 1.3, -0.68);
    s.quadraticCurveTo(0.12, -0.60, 0.02, -0.25);
    s.quadraticCurveTo(-0.04, 0.35, 0.12, 0.74);
    s.closePath();
    s.holes.push(foroTriangolo([[1.2, -0.35], [2.6, 0.52], [4.4, -0.34]], 0.12));
    s.holes.push(foroTriangolo([[5.25, -0.32], [6.35, 0.42], [7.7, -0.25]], 0.10));
    s.holes.push(foroCircolo(8.55, 0.04, 0.24));
    return s;
  }

  function formaPiede3D() {
    const s = new THREE.Shape();
    s.moveTo(-0.10, 0.40);
    s.quadraticCurveTo(0.65, 0.38, 0.95, 0.08);
    s.quadraticCurveTo(1.25, -0.28, 1.43, -0.85);
    s.quadraticCurveTo(1.60, -1.52, 1.50, -1.78);
    s.quadraticCurveTo(1.38, -1.95, 1.16, -1.86);
    s.quadraticCurveTo(0.96, -1.75, 0.98, -1.38);
    s.quadraticCurveTo(1.00, -0.95, 0.82, -0.58);
    s.quadraticCurveTo(0.55, -0.08, 0.02, 0.06);
    s.quadraticCurveTo(-0.22, 0.12, -0.10, 0.40);
    s.closePath();
    return s;
  }

  function vite(parent, x, y, z, raggio = 0.17) {
    const gambo = new THREE.Mesh(new THREE.CylinderGeometry(raggio * 0.55, raggio * 0.55, z * 2 + 0.24, 8), alluminio);
    gambo.rotation.x = Math.PI / 2;
    gambo.position.set(x, y, 0);
    parent.add(gambo);
    for (const dz of [-z - 0.12, z + 0.12]) {
      const testa = new THREE.Mesh(new THREE.CylinderGeometry(raggio, raggio, 0.07, 12), alluminio);
      testa.rotation.x = Math.PI / 2;
      testa.position.set(x, y, dz);
      parent.add(testa);
      const taglio = new THREE.Mesh(new THREE.BoxGeometry(raggio * 1.25, 0.025, 0.03), chip);
      taglio.position.set(x, y, dz + Math.sign(dz) * 0.04);
      parent.add(taglio);
    }
  }

  function gruppoServo(x, y, z, scalaServo) {
    const g = new THREE.Group();
    g.position.set(x, y, z);

    const corpo = new THREE.Mesh(new THREE.BoxGeometry(2.15, 1.05, 1.15), servoScuro);
    corpo.position.x = 1.0;
    g.add(corpo);

    const coperchio = new THREE.Mesh(new THREE.BoxGeometry(2.02, 0.12, 1.05), servoTop);
    coperchio.position.set(1.0, 0.57, 0);
    g.add(coperchio);

    const etichettaS = new THREE.Mesh(new THREE.BoxGeometry(1.0, 0.04, 0.48), etichetta);
    etichettaS.position.set(1.05, 0.64, 0);
    g.add(etichettaS);

    const albero = new THREE.Mesh(new THREE.CylinderGeometry(0.16, 0.16, 0.34, 10), alluminio);
    albero.rotation.x = Math.PI / 2;
    albero.position.set(0.05, 0.1, 0);
    g.add(albero);

    const cornoMesh = new THREE.Mesh(
      new THREE.CylinderGeometry(0.42 * scalaServo, 0.42 * scalaServo, 0.10, 14), corno
    );
    cornoMesh.rotation.x = Math.PI / 2;
    cornoMesh.position.set(0.05, 0.1, 0.34);
    g.add(cornoMesh);

    return g;
  }

  function tavolaCavo(punti, materiale, raggio, parent) {
    const curva = new THREE.CatmullRomCurve3(punti.map(p => new THREE.Vector3(p[0], p[1], p[2])));
    const geo = new THREE.TubeGeometry(curva, 16, raggio, 6, false);
    const mesh = new THREE.Mesh(geo, materiale);
    parent.add(mesh);
    return mesh;
  }

  function textureOmbra() {
    const c = document.createElement('canvas');
    c.width = c.height = 128;
    const ctx = c.getContext('2d');
    const grad = ctx.createRadialGradient(64, 64, 4, 64, 64, 62);
    grad.addColorStop(0, 'rgba(255,255,255,0.85)');
    grad.addColorStop(0.55, 'rgba(255,255,255,0.35)');
    grad.addColorStop(1, 'rgba(255,255,255,0)');
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, 128, 128);
    const tex = new THREE.CanvasTexture(c);
    tex.colorSpace = THREE.SRGBColorSpace;
    return tex;
  }

  function spriteLuce(colore, dimensione) {
    const c = document.createElement('canvas');
    c.width = c.height = 64;
    const ctx = c.getContext('2d');
    const grad = ctx.createRadialGradient(32, 32, 0, 32, 32, 32);
    grad.addColorStop(0, 'rgba(255,255,255,1)');
    grad.addColorStop(0.25, 'rgba(190,245,255,0.75)');
    grad.addColorStop(1, 'rgba(120,220,255,0)');
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, 64, 64);
    const tex = new THREE.CanvasTexture(c);
    const mat = new THREE.SpriteMaterial({
      map: tex, color: colore, transparent: true, opacity: 0.35,
      blending: THREE.AdditiveBlending, depthWrite: false
    });
    const sp = new THREE.Sprite(mat);
    sp.scale.setScalar(dimensione);
    return sp;
  }

  function creaAmbiente(r) {
    const c = document.createElement('canvas');
    c.width = 1024;
    c.height = 512;
    const ctx = c.getContext('2d');

    const fondo = ctx.createLinearGradient(0, 0, 0, 512);
    fondo.addColorStop(0, '#1d2433');
    fondo.addColorStop(0.45, '#121318');
    fondo.addColorStop(1, '#08080a');
    ctx.fillStyle = fondo;
    ctx.fillRect(0, 0, 1024, 512);

    function alone(x, y, raggio, colore) {
      const g = ctx.createRadialGradient(x, y, 0, x, y, raggio);
      g.addColorStop(0, colore);
      g.addColorStop(1, 'rgba(0,0,0,0)');
      ctx.fillStyle = g;
      ctx.fillRect(0, 0, 1024, 512);
    }
    alone(512, 60, 340, 'rgba(255,255,255,0.72)');
    alone(210, 160, 230, 'rgba(255,196,150,0.38)');
    alone(820, 190, 250, 'rgba(110,215,255,0.72)');
    alone(620, 430, 190, 'rgba(255,110,50,0.34)');
    alone(80, 390, 180, 'rgba(120,160,255,0.24)');

    const tex = new THREE.CanvasTexture(c);
    tex.mapping = THREE.EquirectangularReflectionMapping;
    tex.colorSpace = THREE.SRGBColorSpace;
    const pmrem = new THREE.PMREMGenerator(r);
    const env = pmrem.fromEquirectangular(tex).texture;
    pmrem.dispose();
    tex.dispose();
    return env;
  }
}
