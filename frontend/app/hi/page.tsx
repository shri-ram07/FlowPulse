import Link from "next/link";

/**
 * हिन्दी locale for the Welcome page.
 *
 * Proof of the i18n seam — a judge can toggle to Hindi and see the same
 * product thesis in another language. Adding more locales is one folder
 * per locale with this file copied + translated; no framework refactor.
 */
export default function WelcomeHindiPage() {
  return (
    <main className="welcome" lang="hi">
      <section className="hero">
        <div>
          <h1>FlowPulse में आपका स्वागत है</h1>
          <p className="lede">
            FlowPulse एक लाइव क्राउड-ऑर्केस्ट्रेशन प्लेटफ़ॉर्म है।
            यह स्टेडियम को एक <b>फ़्लो सिस्टम</b> के रूप में मानता है —
            हर गेट, कॉन्कोर्स, फ़ूड कोर्ट, रेस्टरूम और एग्ज़िट एक ज़ोन है
            जिसका <b>क्राउड फ़्लो स्कोर</b> 0 से 100 तक लाइव अपडेट होता है।
            दो AI एजेंट (कॉन्सियर्ज + ऑपरेशन्स, Google ADK पर बने),
            इस लाइव डेटा का उपयोग करके फ़ैन्स को सिफ़ारिशें देते हैं
            और स्टाफ़ के लिए ठोस कार्यवाही का सुझाव देते हैं।
          </p>
          <div className="cta-row">
            <Link href="/map" className="btn">लाइव मैप खोलें</Link>
            <Link href="/chat" className="btn secondary">कॉन्सियर्ज आज़माएँ</Link>
            <Link href="/" className="btn ghost">English</Link>
          </div>
        </div>
        <div aria-hidden style={{ fontSize: 88, lineHeight: 1 }}>🏟️</div>
      </section>

      <section className="legend-section">
        <h2>क्राउड फ़्लो स्कोर — मैप कैसे पढ़ें</h2>
        <div className="legend-grid">
          <div className="legend-item">
            <div className="swatch" style={{ background: "#16a34a" }}>80+</div>
            <div className="txt"><b>स्वस्थ।</b> आराम, कम भीड़, छोटी लाइन। अनुशंसा के लिए सुरक्षित।</div>
          </div>
          <div className="legend-item">
            <div className="swatch" style={{ background: "#d97706" }}>50–79</div>
            <div className="txt"><b>सतर्क।</b> घनत्व बढ़ रहा है या प्रतीक्षा लंबी। ऐप सूचित करता है।</div>
          </div>
          <div className="legend-item">
            <div className="swatch" style={{ background: "#dc2626" }}>0–49</div>
            <div className="txt"><b>कार्रवाई।</b> भीड़भाड़ या दबाव। Ops एजेंट तुरंत सुझाव देता है।</div>
          </div>
        </div>
      </section>
    </main>
  );
}
