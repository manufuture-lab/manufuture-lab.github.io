# 실적 Sheet와 홈페이지 동기화

비공개 Google Sheets 커넥터에서 읽은 JSON을 검증해 기존 Hugo 데이터 형식으로 생성합니다. 네트워크, Google 인증, 공개 Sheet URL, 비밀키, Git 커밋·push는 사용하지 않습니다. 기본 실행은 staging 폴더에만 쓰며 실제 반영에는 --apply가 필요합니다.

## 스키마와 원본

- publications-sync.schema.json: 학회·논문·특허·예정일정의 machine key/한국어 header 대응.
- 최초 bootstrap JSON은 공개 소스 원문·체크섬과 고정 ID를 가진 이관 행입니다. 운영 파일은 저장소 바깥 작업 폴더에 보관하고 커밋하지 않습니다. 테스트는 필요한 일부 원문만 담은 tests/fixtures/publications-sync를 사용하므로 운영 bootstrap에 의존하지 않습니다.
- 최초 이관은 공개 학회 52건 + 기존 주석 처리 1건, 논문 24건(게재 승인/출판 20 + 투고/심사 4), 국가별 특허 21건/10묶음, PCT 연계번호 2개입니다. PCT는 총 건수에 포함하지 않습니다.
- **현재 사사 원문·사사 상태·사사 근거·과제 ID는 전부 공란입니다.** 열만 향후 입력용으로 보존합니다. 이번 작업에서는 사사 연결·집계 탭을 만들지 않습니다.
- 관리 ID는 정렬·행 삽입·제목 수정에도 유지합니다. 새 행은 동기화 담당이 고유 ID를 발급해 Sheet에 기록한 뒤 사용합니다. ID 없이 게시하지 않습니다.

입력 JSON:

    {"schema_version": 1, "sheets": {
      "conferences": [], "journals": [], "patents": [], "schedule": []
    }}

각 배열에는 행 객체를 넣습니다. 열 key 대신 스키마의 정확한 한국어 header도 허용하지만 같은 필드를 양쪽 이름으로 중복 입력할 수 없습니다. Sheet 행 정렬은 ID에 영향을 주지 않습니다. 네 탭 모두 읽어야 하며 일부 범위만 읽어 기존 행이 누락되면 기본적으로 중단합니다. 완전히 빈 행은 무시합니다.

네이티브 Google Sheet의 한국어 DATE 셀이 2026. 10. 27 또는 2026. 10. 27.로 반환되면 예정일정의 start_date/end_date 두 열만 YYYY-MM-DD로 정규화합니다. 연도·월·일이 명확한 이 형식만 처리하며 다른 열, 숫자 일련번호, 10/27/2026 같은 다른 표기는 추측해 변환하지 않습니다. 존재하지 않는 날짜도 거부합니다.

선택 보조 탭 acknowledgements/사사는 명시적으로 무시하고 보고서에 표시합니다. 이번에는 만들지 않으며 향후 호환용입니다. 추가 비공개 열은 private_ 접두사 또는 스키마의 새 열로 확장할 수 있습니다.

일반 분리 열을 수정하면 출력에 반영됩니다. citation_raw는 최초 원문 비교용이며 일반 필드 편집을 덮어쓰지 않습니다. format_mode=legacy는 수동 검토가 필요한 예외용이고 구조 열과 병용할 수 없습니다. 최초 53개 학회는 모두 structured이며 저자·제목·형식·학회·장소·연월을 다시 조합하면 원문과 문자 단위로 일치합니다. 기존 오탈자·중복 문구를 임의 교정하지 않았습니다.

논문 저자 서식은 authors_md의 Markdown이 기준입니다. 예를 들어 강조 표기와 공동저자 #를 보존합니다. Sheet 셀의 시각적 굵게/색은 values JSON에 포함되지 않으므로 별도 서식으로 해석하지 않습니다. DOI/PDF 주소, 대표·표지 이미지 경로, 추가 설명은 독립 열입니다. 기존 PDF 자리표시자 #도 초기 이관에서는 보존합니다.

특허는 국가별 출원·등록 한 건이 한 행입니다. 같은 발명은 family_id로 묶고 명칭·PCT·묶음 설명은 그 묶음의 첫 행에만 둡니다. 첫 행을 보류할 때는 다음 공개 행으로 묶음 메타데이터를 옮깁니다. 번호는 쉼표·선행 0·소수점이 사라지지 않도록 텍스트로 저장합니다.

## 공개 조건과 정렬

- 게시 승인만 공개 대상으로 생성합니다. 검토 중·보류는 제외합니다.
- 학회는 미래 날짜가 아니면서 기존 실적/발표 완료/프로그램·프로시딩 확인인 경우만 공개합니다. 마지막 상태는 자료 확인이며 실제 발표 목격을 뜻하지 않습니다.
- 예정/발표 여부 확인/취소, 미래 날짜는 승인 상태라도 제외합니다. 미승인 미래 행은 미확인 저자·형식 등을 비워 둘 수 있습니다.
- 날짜 정밀도는 YYYY, YYYY-MM, YYYY-MM-DD로 보존합니다. 기존 학회는 원문에 있는 연월까지만 기록합니다. 학회 citation 생성에는 최소 연월이 필요합니다. 달 단위 날짜는 그 달 시작으로 비교하되, 날짜가 지났다는 이유로 진행 상태나 게시 승인을 바꾸지 않습니다.
- 프로그램·프로시딩 확인 상태에 이번 달처럼 아직 끝나지 않은 연월만 입력하면 공개하지 않습니다. 정확한 행사 날짜를 입력하거나 해당 달 전체가 지난 뒤 확인해야 합니다. 기존 실적의 연월 표기는 그대로 보존합니다.
- 학회는 날짜 내림차순, 같은 날짜는 legacy_order, 마지막 동률은 ID 순입니다. 기존 shortcode가 전체 건수부터 역순 번호를 만들기 때문에 과거 항목 삽입/숨김의 번호 변화는 conference_renumbered_ids에 경고로 기록합니다.
- 논문 display_order는 고정 번호입니다. 기존 번호 변경과 중복은 차단합니다. 새 게재 승인/출판 논문에는 다음 미사용 번호를 지정합니다.
- 특허는 family_order, filing_order로 묶음·국가 순서를 유지합니다.

공개 출력은 명시된 열만 사용합니다. 세부 장소 venue, 국제/국내 scope, 사사·과제 정보, 근거 URL/경로, 발표자·교수 역할, 예정일정 메모, private_ 열은 홈페이지에 넣지 않습니다. location은 현재 인용 형식의 공개 도시·국가 열입니다.

비공개 데이터는 staging/next-baseline.json에는 남으므로 **staging 전체를 배포하지 않습니다.** 검토·배포 대상은 아래 세 제품 파일뿐입니다.

    data/conferences.yaml
    data/journals.yaml
    content/publications/patent/_index.md

## 설치와 실행

Python 3.9 이상과 scripts/requirements-publications-sync.txt의 PyYAML 6.0.2가 필요합니다. 나머지는 표준 라이브러리만 사용합니다. 권장 Python은 3.12이며 프로젝트 가상 환경 또는 별도 도구 디렉터리에 의존성을 설치합니다.

    python -m pip install -r scripts/requirements-publications-sync.txt
    python scripts/publications_sync.py bootstrap --output ../build-tools/publications-state.json
    python scripts/publications_sync.py sync --input ../build-tools/sheet-input.json --baseline ../build-tools/publications-state.json --staging ../build-tools/publications-staging

현재 Codex 번들 Python에는 PyYAML이 없어 ../build-tools/publications-sync-deps에 별도 설치했습니다. 이 환경에서는 먼저 PowerShell의 PYTHONPATH를 해당 경로로 지정합니다.

    $env:PYTHONPATH = (Resolve-Path '../build-tools/publications-sync-deps').Path

번들 Python 경로는 Codex workspace dependencies 도구로 확인합니다. --repo 옵션은 서브명령 앞에 두며 기본값은 스크립트가 속한 저장소입니다.

bootstrap 출력, 운영 baseline, 알림 완료 상태, staging은 저장소 바깥 경로만 허용합니다. static/ 아래나 숨김 폴더라도 저장소 안에는 만들 수 없습니다. 입력 JSON도 비공개 작업 폴더에서 관리합니다.

변경이 없으면 원래 파일 바이트·줄바꿈·주석을 그대로 출력합니다. 변경된 YAML은 의미를 보존해 재직렬화하고, 특허 문서는 기존 frontmatter의 본문 블록만 바꿉니다. 원본 체크섬이 현재 저장소와 다르면 중단하므로 다른 작업의 수정을 덮어쓰지 않습니다.

검토 후 같은 sync 명령에 --apply를 추가하면 생성 파일을 반영하고 운영 baseline을 갱신합니다. 적용 직전 체크섬 재확인과 동시 실행 lock을 사용합니다. 이전 파일과 baseline은 staging에 보관하며 오류 시 이미 쓴 소스를 되돌립니다. 비정상 종료 후 lock이 남으면 실제 실행 여부를 확인한 뒤 수동 처리합니다. --allow-missing은 의도적으로 제거할 행을 확인했을 때만 사용하는 명시적 예외입니다.

프로그램은 빌드·커밋·push를 하지 않습니다. 반영 담당이 생성 diff와 report.json을 확인하고 Hugo production 빌드를 통과시킨 후 승인된 범위에서 게시합니다. 운영 baseline이 저장소와 충돌하면 단순 재생성으로 과거 ID를 바꾸지 말고 기존 ID를 유지하며 변경 내역을 대조합니다.

## 종료 후 확인과 알림

예정일정은 홈페이지 출력 대상이 아닙니다. remind_days가 공란이면 시작 전 알림은 없습니다. 값이 있으면 7,1,0처럼 일수를 지정하고 해당 날짜에만 시작 알림을 만듭니다.

예정 상태의 행은 **종료일 다음날부터 참가·발표 여부 확인 질문**을 한 번 만듭니다. 종료일이 없으면 단일 날짜 행사로 보고 시작일을 사용합니다. 오프라인으로 당일을 놓쳐도 다음 실행에서 질문합니다. 알림 ID는 일정ID:종료일:after_event입니다. 완료·취소·확인 필요 상태는 알리지 않으며 실제 발표 여부·게시 승인·진행 상태를 자동 변경하지 않습니다.

notifications.json은 발송 대기 자료입니다. 생성만으로 발송 완료로 취급하지 않습니다. heartbeat가 사용자에게 실제 전달한 뒤 완료 ID를 기록합니다.

    python scripts/publications_sync.py ack-notifications --state ../build-tools/publications-delivered.json --id "일정ID:2026-11-15:after_event"

이후 sync 명령에 --delivered ../build-tools/publications-delivered.json을 넣으면 중복을 억제합니다. 기본 날짜는 한국 시간이며 재현 검증에는 --today YYYY-MM-DD를 사용합니다.

heartbeat는 비공개 커넥터로 관리 행 전체를 제한 범위 읽기 → JSON 저장 → dry-run → 실제 변경/새 질문만 보고하는 순서로 실행합니다. 변경과 알림이 없으면 조용히 종료합니다. 로그인·접근 권한을 이 프로그램이 우회하거나 보관하지 않습니다.

## 검증

    python -m unittest discover -s tests -p test_publications_sync.py -v

테스트는 임시 저장소에서만 실행합니다. 최초 이관 바이트 보존, 일반 필드 반영, 미래/미승인 제외, 비공개 열 누출 방지, 누락·중복·충돌 차단, 저자·번호·특허 묶음 보존, 알림 중복 억제·종료 후 누락 보충, 명시적 apply와 동시 실행 lock을 검증합니다.
