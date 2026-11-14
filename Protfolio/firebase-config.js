// Firebase Cloud Sync Engine for Sojol Visuals Portfolio
const firebaseConfig = {
  apiKey: "AIzaSyA4S2yVPhIxa2QybF26rbonN6bEB5Wsl-Y",
  authDomain: "sojol-portfolio.firebaseapp.com",
  projectId: "sojol-portfolio",
  storageBucket: "sojol-portfolio.firebasestorage.app",
  messagingSenderId: "481589225919",
  appId: "1:481589225919:web:08524e6f0d871e758a190a",
  measurementId: "G-MQP5FXS0DJ"
};

// Initialize Firebase App
let firebaseApp = null;
let firestoreDb = null;
let isFirebaseReady = false;

try {
  if (typeof firebase !== 'undefined') {
    if (!firebase.apps.length) {
      firebaseApp = firebase.initializeApp(firebaseConfig);
    } else {
      firebaseApp = firebase.app();
    }
    firestoreDb = firebase.firestore();
    isFirebaseReady = true;
    console.log("[Firebase] Cloud Engine connected successfully.");
  }
} catch (err) {
  console.warn("[Firebase] Init error, fallback to local data:", err);
}

// Save portfolio data to Firestore Cloud
async function saveToFirebaseCloud(data) {
  if (!isFirebaseReady || !firestoreDb) {
    console.warn("[Firebase] Not initialized, skipped cloud save.");
    return false;
  }
  try {
    const cleanData = JSON.parse(JSON.stringify(data));
    cleanData._lastUpdated = Date.now();
    await firestoreDb.collection("portfolio").doc("data").set(cleanData);
    console.log("[Firebase] Successfully saved to Firestore cloud!");
    return true;
  } catch (err) {
    console.error("[Firebase] Error saving to Firestore:", err);
    return false;
  }
}

// Load portfolio data from Firestore Cloud
async function loadFromFirebaseCloud() {
  if (!isFirebaseReady || !firestoreDb) return null;
  try {
    const docSnap = await firestoreDb.collection("portfolio").doc("data").get();
    if (docSnap.exists) {
      console.log("[Firebase] Loaded live data from Firestore cloud.");
      return docSnap.data();
    }
  } catch (err) {
    console.warn("[Firebase] Error reading from Firestore:", err);
  }
  return null;
}

// Real-time listener for live portfolio updates
function listenToFirebaseCloud(callback) {
  if (!isFirebaseReady || !firestoreDb) return () => {};
  try {
    return firestoreDb.collection("portfolio").doc("data").onSnapshot((docSnap) => {
      if (docSnap.exists) {
        const liveData = docSnap.data();
        callback(liveData);
      }
    }, (err) => {
      console.warn("[Firebase] Snapshot listener error:", err);
    });
  } catch (err) {
    console.warn("[Firebase] Failed to attach listener:", err);
    return () => {};
  }
}

// ===== REAL-TIME VISITOR ANALYTICS & GEO ENGINE WITH CLIENT/EMAIL TRACKING =====
async function logVisitorHit() {
  if (!isFirebaseReady || !firestoreDb) return;
  try {
    // 1. Exclude Admin & Previews from polluting analytics
    if (localStorage.getItem('sojol_admin_authenticated') === 'true' || location.search.includes('admin') || location.hash.includes('admin')) {
      return;
    }

    // 2. Extract Client Tag / Email / Campaign from URL
    const urlParams = new URLSearchParams(window.location.search);
    const clientTag = (urlParams.get('client') || urlParams.get('email') || urlParams.get('c') || urlParams.get('to') || urlParams.get('ref') || urlParams.get('utm_campaign') || urlParams.get('source') || '').trim();

    // 3. Session guard (If it's a tracked client email link, always log so Sojol gets instant notification)
    const sessionKey = 'sojol_logged_session';
    const isNewSession = !sessionStorage.getItem(sessionKey);
    if (!clientTag && !isNewSession) return;
    sessionStorage.setItem(sessionKey, '1');

    // 4. Fetch rich geo info with strict timeout
    let geo = { country: 'Unknown', city: '', region: '', country_code: 'UN', flag: '🌍', isp: '', ip: '', lat: null, lon: null };
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 2800);
      const res = await fetch('https://ipwho.is/', { signal: controller.signal });
      clearTimeout(timeoutId);
      if (res.ok) {
        const d = await res.json();
        if (d && d.success) {
          geo = {
            country: d.country || 'Unknown',
            city: d.city || '',
            region: d.region || '',
            country_code: d.country_code || '',
            flag: d.flag?.emoji || '🌍',
            isp: d.connection?.isp || d.connection?.org || '',
            ip: d.ip || '',
            lat: d.latitude || null,
            lon: d.longitude || null
          };
        }
      }
    } catch (e) {}

    // 5. Device & OS & Browser info
    const ua = navigator.userAgent || '';
    let deviceType = 'Desktop';
    if (/iPad|tablet/i.test(ua)) deviceType = 'Tablet';
    else if (/Mobile|Android|iPhone/i.test(ua)) deviceType = 'Mobile';

    let os = 'Windows';
    if (/iPhone|iPad|iPod/i.test(ua)) os = 'iOS';
    else if (/Macintosh|Mac OS X/i.test(ua)) os = 'macOS';
    else if (/Android/i.test(ua)) os = 'Android';
    else if (/Linux/i.test(ua)) os = 'Linux';

    let browser = 'Chrome';
    if (/Firefox/i.test(ua)) browser = 'Firefox';
    else if (/Edg/i.test(ua)) browser = 'Edge';
    else if (/Safari/i.test(ua) && !/Chrome/i.test(ua)) browser = 'Safari';
    else if (/Opera|OPR/i.test(ua)) browser = 'Opera';

    const screenRes = (typeof window !== 'undefined' && window.screen) ? `${window.screen.width}x${window.screen.height}` : '';
    const timestamp = Date.now();
    const dateStr = new Date().toISOString().slice(0, 10);
    const referrer = document.referrer ? new URL(document.referrer).hostname : (clientTag ? `Email/DM Pitch (${clientTag})` : 'Direct Link');

    const hit = {
      country: geo.country,
      city: geo.city,
      region: geo.region,
      country_code: geo.country_code,
      flag: geo.flag,
      isp: geo.isp,
      ip: geo.ip ? geo.ip.replace(/\.\d+$/, '.***') : '',
      lat: geo.lat,
      lon: geo.lon,
      device: `${deviceType} (${os})`,
      browser,
      screenRes,
      clientTag,
      referrer,
      timestamp
    };

    const docRef = firestoreDb.collection("analytics").doc("overview");
    await firestoreDb.runTransaction(async (transaction) => {
      const doc = await transaction.get(docRef);
      let data = doc.exists ? doc.data() : { totalVisits: 0, uniqueSessions: 0, daily: {}, countries: {}, recent: [], clientLeads: {} };

      data.totalVisits = (data.totalVisits || 0) + 1;
      if (isNewSession) {
        data.uniqueSessions = (data.uniqueSessions || 0) + 1;
      }

      data.daily = data.daily || {};
      data.daily[dateStr] = (data.daily[dateStr] || 0) + 1;

      data.countries = data.countries || {};
      const cName = geo.country || 'Unknown';
      data.countries[cName] = data.countries[cName] || { count: 0, flag: geo.flag, code: geo.country_code };
      data.countries[cName].count = (data.countries[cName].count || 0) + 1;

      // Track identified clients/emails specifically
      if (clientTag) {
        data.clientLeads = data.clientLeads || {};
        data.clientLeads[clientTag] = {
          clientTag,
          lastSeen: timestamp,
          views: ((data.clientLeads[clientTag]?.views) || 0) + 1,
          location: [geo.city, geo.country].filter(Boolean).join(', ') || 'Unknown Location',
          flag: geo.flag,
          isp: geo.isp,
          device: `${deviceType} (${os})`,
          browser
        };
      }

      data.recent = data.recent || [];
      data.recent.unshift(hit);
      if (data.recent.length > 80) {
        data.recent = data.recent.slice(0, 80);
      }

      data.lastUpdated = timestamp;
      transaction.set(docRef, data, { merge: true });
    });
    console.log('[Analytics] Visitor hit logged:', geo.country, geo.city, clientTag ? `(Client: ${clientTag})` : '');
  } catch (err) {
    console.warn('[Analytics] Log error:', err);
  }
}

// Real-time listener for Analytics in Admin Panel
function listenToAnalytics(callback) {
  if (!isFirebaseReady || !firestoreDb) return () => {};
  try {
    return firestoreDb.collection("analytics").doc("overview").onSnapshot((docSnap) => {
      if (docSnap.exists) {
        callback(docSnap.data());
      }
    }, (err) => {
      console.warn("[Analytics] Snapshot error:", err);
    });
  } catch (err) {
    console.warn("[Analytics] Failed to listen to analytics:", err);
    return () => {};
  }
}
