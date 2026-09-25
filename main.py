import cv2
import mediapipe as mp
import numpy as np
import time

# --------------------------------------------------
# MediaPipe FaceMesh (yüz landmark tespiti)
# --------------------------------------------------
mp_yuz_ag = mp.solutions.face_mesh

yuz_ag = mp_yuz_ag.FaceMesh(
    static_image_mode=False,   # video akışı
    max_num_faces=1,           # tek yüz
    refine_landmarks=True      # göz/dudak daha hassas
)

# --------------------------------------------------
# Kamera başlat
# --------------------------------------------------
kamera = cv2.VideoCapture(0)

# Pencere ayarları
cv2.namedWindow("Surucu Dikkat Takibi", cv2.WINDOW_NORMAL)
cv2.resizeWindow("Surucu Dikkat Takibi", 1080, 720)

# --------------------------------------------------
# Landmark indexleri
# --------------------------------------------------
sol_goz_noktalari = [33, 160, 158, 133, 153, 144]
agiz_noktalari = [78, 13, 308, 14]

burun_ucu_noktasi = 1
cene_noktasi = 152
sol_yuz_noktasi = 234
sag_yuz_noktasi = 454
alin_noktasi = 10

# --------------------------------------------------
# Eşik değerler
# --------------------------------------------------
goz_kapali_esik = 0.22
kapali_frame_esigi = 20

agiz_aciklik_esik = 0.06
esneme_frame_esigi = 15

bas_asagi_esik = 0.65
bas_yan_esik = 0.15

# --------------------------------------------------
# Sayaçlar
# --------------------------------------------------
kapali_frame = 0
agiz_frame = 0
esneme_sayisi = 0

onceki_zaman = 0

# --------------------------------------------------
# Renkler
# --------------------------------------------------
BEYAZ = (255,255,255)
YESIL = (0,255,0)
KIRMIZI = (0,0,255)
TURUNCU = (0,165,255)
MOR = (255,0,255)
SARI = (0,255,255)
CIYAN = (255,255,0)

# --------------------------------------------------
# Nokta alma fonksiyonu
# --------------------------------------------------
def nokta_al(lm, i, w, h):
    return np.array([int(lm[i].x*w), int(lm[i].y*h)])

# --------------------------------------------------
# Göz oranı hesaplama
# --------------------------------------------------
def goz_orani(lm, idx, w, h):
    pts = [(int(lm[i].x*w), int(lm[i].y*h)) for i in idx]
    A = np.linalg.norm(np.array(pts[1]) - np.array(pts[5]))
    B = np.linalg.norm(np.array(pts[2]) - np.array(pts[4]))
    C = np.linalg.norm(np.array(pts[0]) - np.array(pts[3]))
    return (A+B)/(2*C) if C!=0 else 0

# --------------------------------------------------
# Ağız oranı (esneme)
# --------------------------------------------------
def agiz_orani(lm, idx, w, h):
    pts = [(int(lm[i].x*w), int(lm[i].y*h)) for i in idx]
    dikey = np.linalg.norm(np.array(pts[1]) - np.array(pts[3]))
    yatay = np.linalg.norm(np.array(pts[0]) - np.array(pts[2]))
    return dikey/yatay if yatay!=0 else 0

# --------------------------------------------------
# Dikkat skoru
# --------------------------------------------------
def skor_hesapla(kapali, esneme, bas):
    skor = 100
    if kapali >= kapali_frame_esigi: skor -= 40
    skor -= min(esneme*5,20)
    if bas == "ASAGI": skor -= 30
    if bas in ["SAG","SOL"]: skor -= 10
    return max(skor,0)

# --------------------------------------------------
# Risk durumu
# --------------------------------------------------
def risk_hesapla(kapali, esneme, bas):
    if kapali>=kapali_frame_esigi or bas=="ASAGI":
        return "YUKSEK", KIRMIZI
    if esneme>=3 or bas in ["SAG","SOL"]:
        return "ORTA", TURUNCU
    return "NORMAL", YESIL

# --------------------------------------------------
# ANA DÖNGÜ
# --------------------------------------------------
while True:
    ret, frame = kamera.read()
    if not ret: break

    frame = cv2.flip(frame,1)
    h,w,_ = frame.shape

    # FPS hesaplama
    simdi = time.time()
    fps = 1/(simdi-onceki_zaman) if onceki_zaman!=0 else 0
    onceki_zaman = simdi

    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    sonuc = yuz_ag.process(rgb)

    goz_durum="YOK"
    bas_durum="NORMAL"
    risk_text="YOK"
    risk_color=TURUNCU
    skor=100
    uyari_mesaji=""

    if sonuc.multi_face_landmarks:
        lm = sonuc.multi_face_landmarks[0].landmark

        # oranlar
        ear = goz_orani(lm, sol_goz_noktalari, w, h)
        mar = agiz_orani(lm, agiz_noktalari, w, h)

        # landmark noktaları
        burun = nokta_al(lm, burun_ucu_noktasi, w, h)
        sol = nokta_al(lm, sol_yuz_noktasi, w, h)
        sag = nokta_al(lm, sag_yuz_noktasi, w, h)
        alin = nokta_al(lm, alin_noktasi, w, h)
        cene = nokta_al(lm, cene_noktasi, w, h)

        # YÜZ NOKTALARINI ÇİZ
        for i in sol_goz_noktalari:
            cv2.circle(frame, tuple(nokta_al(lm,i,w,h)), 2, YESIL, -1)

        for i in agiz_noktalari:
            cv2.circle(frame, tuple(nokta_al(lm,i,w,h)), 2, MOR, -1)

        cv2.circle(frame, tuple(burun), 4, SARI, -1)
        cv2.circle(frame, tuple(cene), 4, SARI, -1)
        cv2.circle(frame, tuple(sol), 4, CIYAN, -1)
        cv2.circle(frame, tuple(sag), 4, CIYAN, -1)
        cv2.circle(frame, tuple(alin), 4, CIYAN, -1)

        # baş analizi
        merkez = (sol[0]+sag[0])/2
        kayma = (burun[0]-merkez)/max((sag[0]-sol[0]),1)
        dikey = (burun[1]-alin[1])/max((cene[1]-alin[1]),1)

        if dikey>bas_asagi_esik: bas_durum="ASAGI"
        elif kayma>bas_yan_esik: bas_durum="SAG"
        elif kayma<-bas_yan_esik: bas_durum="SOL"
        else: bas_durum="NORMAL"

        # göz
        if ear<goz_kapali_esik:
            kapali_frame+=1
            goz_durum="KAPALI"
        else:
            kapali_frame=0
            goz_durum="ACIK"

        # esneme
        if mar>agiz_aciklik_esik:
            agiz_frame+=1
        else:
            if agiz_frame>=esneme_frame_esigi:
                esneme_sayisi+=1
            agiz_frame=0

        # ÜST UYARI MESAJI
        if kapali_frame >= kapali_frame_esigi:
            uyari_mesaji = "GOZ KAPANMASI ALGILANDI"
        elif agiz_frame >= esneme_frame_esigi:
            uyari_mesaji = "ESNEME ALGILANDI"
        elif bas_durum in ["SAG", "SOL"]:
            uyari_mesaji = "SURUCU BASKA YONE BAKIYOR"
        else:
            uyari_mesaji = ""

        # risk ve skor
        risk_text,risk_color = risk_hesapla(kapali_frame,esneme_sayisi,bas_durum)
        skor = skor_hesapla(kapali_frame,esneme_sayisi,bas_durum)

    # ALT ORTA YAZI
    if uyari_mesaji != "":
        text_size = cv2.getTextSize(uyari_mesaji, cv2.FONT_HERSHEY_SIMPLEX, 0.9, 3)[0]
        text_x = int((w - text_size[0]) / 2)

        cv2.putText(frame, uyari_mesaji, (text_x, h - 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, KIRMIZI, 3)

    # ŞEFFAF PANEL
    overlay = frame.copy()
    cv2.rectangle(overlay,(10,10),(260,140),(0,0,0),-1)
    cv2.rectangle(overlay,(w-220,10),(w-10,110),(0,0,0),-1)
    frame = cv2.addWeighted(overlay,0.4,frame,0.6,0)

    # yazılar
    cv2.putText(frame,f"Goz: {goz_durum}",(20,40),
                cv2.FONT_HERSHEY_SIMPLEX,0.6,BEYAZ,2)

    cv2.putText(frame,f"Esneme: {esneme_sayisi}",(20,70),
                cv2.FONT_HERSHEY_SIMPLEX,0.6,BEYAZ,2)

    cv2.putText(frame,f"Bas: {bas_durum}",(20,100),
                cv2.FONT_HERSHEY_SIMPLEX,0.6,BEYAZ,2)

    cv2.putText(frame,"Risk:",(w-200,40),
                cv2.FONT_HERSHEY_SIMPLEX,0.6,BEYAZ,2)

    cv2.putText(frame,risk_text,(w-200,70),
                cv2.FONT_HERSHEY_SIMPLEX,0.8,risk_color,3)

    cv2.putText(frame,f"Skor: {skor}",(w-200,100),
                cv2.FONT_HERSHEY_SIMPLEX,0.6,BEYAZ,2)

    # bar
    bar_w = int((skor/100)*150)
    cv2.rectangle(frame,(w-200,120),(w-50,140),BEYAZ,2)
    cv2.rectangle(frame,(w-200,120),(w-200+bar_w,140),risk_color,-1)

    # fps
    cv2.putText(frame,f"FPS:{int(fps)}",(w-100,h-20),
                cv2.FONT_HERSHEY_SIMPLEX,0.6,BEYAZ,2)

    cv2.imshow("Surucu Dikkat Takibi", frame)

    if cv2.waitKey(1)&0xFF==ord('q'):
        break

kamera.release()
cv2.destroyAllWindows()