# MIKU GOODS RADAR ♪

하츠네 미쿠 굿즈/콜라보/피규어 소식(일본·중국·한국·글로벌)을 **6시간마다 자동 수집**하는 정적 홈페이지.
GitHub Actions + GitHub Pages만으로 동작합니다. (서버·비용 0)

## 구조

```
index.html        ← 화면 (data.json 표시, 지금 업데이트 버튼, 스토어 바로가기)
fetch_news.py     ← 수집 (Google News RSS 4개 언어 + Mikufan + VNN, 썸네일·카테고리 포함)
data.json         ← 수집 결과 (Actions가 자동 갱신)
og-image.png      ← 링크 공유용 미리보기 이미지
.github/workflows/update.yml  ← push 시 1회 + 6시간마다 + 버튼/수동 실행
```

## 설치 (5분)

1. **GitHub 새 저장소 생성** — Public
2. **파일 전체 push** — `.github` 폴더 포함
   → push하는 순간 **첫 수집이 자동 실행**됩니다 (Actions 탭 안 찾아도 됨)
3. **Pages 켜기** — Settings → Pages → Branch: `main` / `(root)` → Save
4. 1~2분 뒤 `https://<아이디>.github.io/<저장소명>/` 접속 — 끝

## "Actions 탭"은 어디?

저장소 페이지 **상단 가로 메뉴**: `Code · Issues · Pull requests · ▶Actions · Projects …`
(안 보이면: Settings → Actions → General → "Allow all actions" 선택)
실행 기록 확인이나 수동 실행(Run workflow)할 때만 쓰면 됩니다.

## "지금 업데이트" 버튼 설정 (1회)

버튼을 처음 누르면 GitHub 토큰을 물어봅니다:

1. GitHub 우상단 프로필 → **Settings** → 맨 아래 **Developer settings**
2. **Personal access tokens → Fine-grained tokens → Generate new token**
3. Repository access: **Only select repositories** → 이 저장소 선택
4. Permissions → Repository permissions → **Actions: Read and write**
5. Generate → 토큰 복사 → 사이트 버튼에 붙여넣기

토큰은 **내 브라우저(localStorage)에만 저장**되고 어디로도 전송되지 않습니다.
잘못 입력했으면 "토큰 재설정" 클릭.

## 타오바오 스토어 (MOEYU / bilibili 旗舰店)

Tmall은 로그인 장벽·봇 차단 때문에 자동 수집이 불가능합니다.
대신 화면 상단에 **미쿠(初音) 키워드 검색 딥링크 버튼**을 넣어 원클릭으로 신상품을 확인하도록 했습니다.

## 커스터마이즈

- 수집 주기: `update.yml`의 `cron` (예: `0 */3 * * *` = 3시간)
- 키워드/소스: `fetch_news.py`의 `SOURCES`, `GOODS_KW`, `FIGURE_KW`
- 표시 개수: `MAX_ITEMS` (기본 80)

## 로컬 테스트

```bash
pip install feedparser requests
python fetch_news.py
python -m http.server   # http://localhost:8000
```

---
비공식 팬 프로젝트 · Hatsune Miku © Crypton Future Media, INC. (piapro.net)
