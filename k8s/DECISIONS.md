# Scelte di design del deploy k8s

Documento di accompagnamento ai manifest in `k8s/`. Spiega **perché** ogni cosa è stata fatta così, in modo che tu possa difenderle in tesi/colloquio o modificarle con cognizione di causa.

---

## 1. Perché k3s (e non k8s "vanilla" o GKE)

**k3s** è una distribuzione leggera di Kubernetes mantenuta da Rancher/SUSE. Single binary, ~50MB di RAM per il control plane, certificata CNCF. Le API sono identiche a k8s standard, quindi tutto ciò che impari/scrivi è portabile.

- **Vs Kubernetes vanilla (kubeadm)**: kubeadm richiede installare/configurare manualmente etcd, kube-proxy, CNI, ecc. k3s impacchetta tutto (etcd o sqlite, flannel, containerd, traefik, local-path) in un comando. Per un cluster a 3 nodi è la scelta razionale.
- **Vs GKE**: GKE è managed → paghi (€70/mese minimo per il control plane) e perdi controllo sui nodi. Se l'obiettivo è imparare/dimostrare le competenze su k8s, k3s su VM è didatticamente più rilevante. GKE ha senso quando vuoi delegare l'ops, non quando vuoi mostrarla.

**Topologia 1 master + 2 worker**: minima per avere parallelismo reale tra nodi. Non è HA (se cade il master, il cluster perde il control plane finché non torna su) — per HA servirebbero 3 master con etcd embedded. Per il tuo caso è sovradimensionato.

---

## 2. Storage: perché Longhorn

Il problema centrale di un cluster bare-metal con servizi stateful (Postgres, OpenSearch, SeaweedFS) è che **i PVC devono "seguire" i pod** quando vengono ri-schedulati su un nodo diverso. Le opzioni erano tre:

### Local-path (default k3s)
Il PVC è una cartella sul disco del nodo dove il pod gira. Se il pod viene ri-schedulato su un altro nodo, **trova un PVC vuoto** e perde i dati. Inadatto per dati di produzione.

### NFS
Una VM fa da file server, le altre montano la directory remota. Funziona, ma:
- Single point of failure: se il nodo NFS muore, tutti i PVC sono unreachable.
- Performance scarse per database (Postgres su NFS è uno scenario noto per data corruption se la versione NFS è < v4 con locking corretto).
- Nessuno snapshot integrato.

### Longhorn
Storage distribuito cloud-native, sviluppato da Rancher (stessi di k3s). Funziona così:
- Ogni PVC viene **replicato su N nodi** (default 3). I dati di Postgres stanno fisicamente su tutti e 3 i nodi del cluster.
- Se il pod migra, Longhorn monta il volume dal nodo locale o lo serve via TCP da un altro nodo (block device esposto via iSCSI).
- UI integrata per snapshot, backup verso S3/NFS, restore.
- Replication, thin provisioning, encryption.

**Costo**: ~500MB di RAM per nodo per i pod Longhorn (instance-manager, engine). Su VM con almeno 4GB è accettabile.

**Requisito**: `open-iscsi` installato sui nodi. È nel README.

**Trade-off vs managed (Cloud SQL + GCS)**: Cloud SQL toglie tutta la gestione del DB ma costa minimo ~25€/mese e ti vincola al provider. GCS al posto di SeaweedFS richiederebbe modifiche al codice (l'SDK S3 funziona con GCS in modalità interoperability, ma non è 100% trasparente). Per il tuo progetto Longhorn è la scelta corretta: didatticamente più ricco, controllo totale, zero costi extra.

---

## 3. Ingress: perché Traefik (lasciato di default)

k3s installa **Traefik** come ingress controller di default. L'alternativa standard è **ingress-nginx**.

- Funzionalmente per il tuo caso (un dominio, un frontend + un backend) sono equivalenti.
- Traefik viene già installato e mantenuto da k3s → un componente in meno da gestire.
- Ingress-nginx è più diffuso → più esempi online. Vantaggio reale solo quando ti scontri con configurazioni esotiche.

Decisione: **lascio Traefik**. Niente `--disable traefik` nell'install di k3s.

L'`Ingress` (`30-ingress.yaml`) usa la API standard `networking.k8s.io/v1` con annotazioni Traefik. Funziona anche se in futuro sostituisci con ingress-nginx (basta cambiare le annotation).

### Perché un solo hostname per frontend e backend

Configurazione:
- `https://dms.example.com/` → frontend
- `https://dms.example.com/api/*` → backend

Vantaggio: **niente CORS**. Il browser vede frontend e backend sullo stesso origin, quindi niente preflight, niente header `Access-Control-*` da configurare, niente errori in console.

L'alternativa (`frontend.example.com` + `api.example.com`) richiederebbe configurare CORS lato FastAPI e gestire cookie cross-origin con `SameSite=None; Secure`.

---

## 4. TLS: cert-manager + Let's Encrypt

**cert-manager** è il controller k8s standard per certificati TLS. Watcha le risorse `Ingress` con l'annotazione `cert-manager.io/cluster-issuer`, parla con Let's Encrypt via ACME, completa la sfida HTTP-01 (Let's Encrypt fa una richiesta a `/.well-known/acme-challenge/...`, cert-manager fa rispondere il cluster), riceve il certificato e lo salva come Secret k8s. L'Ingress lo monta automaticamente.

Vantaggi:
- Certificato gratuito (Let's Encrypt).
- Rinnovo automatico ogni 60 giorni.
- Zero gestione manuale di chiavi private.

Alternative considerate:
- **Certificato self-signed**: ok per test, ma il browser dà warning.
- **Cloudflare in front**: aggiunge un layer (CDN + TLS Cloudflare), funziona ma richiede DNS su Cloudflare.

---

## 5. ConfigMap vs Secret: cosa è andato dove

Distinzione netta:

**Secret** (`dms-secrets`, file `02-secret.example.yaml`): tutto ciò che è sensibile.
- credenziali Postgres
- chiavi S3
- `EMAIL_ENCRYPTION_KEY`
- `CUSTOM_API_KEY` (chiave API del modello AI)

**ConfigMap** (`dms-config`, file `01-configmap.yaml`): configurazione non sensibile, può stare in git.
- URL dei servizi interni (`S3_ENDPOINT`, `OPENSEARCH_URL`, `MCP_SERVER_URL`)
- `MODEL_NAME`, `BASE_URL`, `EMBEDDING_MODEL_NAME`

**Perché questa separazione conta**:
1. I Secret possono essere cifrati a riposo (`encryption-config` di k8s), le ConfigMap no.
2. Le RBAC permettono di dare accesso alle ConfigMap senza dare accesso ai Secret.
3. Il `02-secret.yaml` reale (con i valori) **non va committato**. La versione `.example` con placeholder sì.

**Evoluzione consigliata**: per non avere segreti in chiaro neanche localmente, usare uno di:
- **SealedSecrets** (Bitnami): cifra i Secret con chiave pubblica del cluster → committabili.
- **External Secrets Operator** + **GCP Secret Manager**: i segreti vivono in GCP, il cluster li sincronizza automaticamente. Più pulito per ambiente GCP.

---

## 6. StatefulSet vs Deployment

Regola applicata:
- **StatefulSet** quando il pod ha **identità persistente + PVC dedicato**: Postgres, OpenSearch, SeaweedFS master/volume/filer.
- **Deployment** per stateless: backend, frontend, mcp-server, email-poller, agent-worker, tika, SeaweedFS S3 gateway.

Perché lo StatefulSet è importante per Postgres:
- Il pod si chiama sempre `postgres-0`, non `postgres-randomhash`.
- Il PVC `data-postgres-0` rimane associato a quel nome anche dopo restart.
- Garantisce un solo pod alla volta (no race su scrittura su disco).
- Scaling ordinato (ma con replica 1 non rilevante).

SeaweedFS-S3 è invece un **Deployment** perché è un gateway stateless: parla con il filer via rete e non tiene dati propri.

---

## 7. Service: headless (`clusterIP: None`) vs normale

Per gli StatefulSet ho usato `clusterIP: None` (**headless Service**). Differenza:

- **Service normale**: il DNS risolve in un ClusterIP virtuale, kube-proxy fa load balancing tra i pod.
- **Headless Service**: il DNS risolve direttamente negli IP dei pod. Necessario per StatefulSet quando ti serve raggiungere un pod specifico (es. `postgres-0.postgres.dms.svc.cluster.local`).

Per repliche=1 è quasi indifferente, ma è la best practice per StatefulSet (e ti tornerà utile se in futuro fai HA Postgres con repliche).

Per le app stateless ho usato Service normali (con ClusterIP) perché il load balancing automatico è quello che vuoi.

---

## 8. Init containers al posto di `depends_on`

Docker Compose ha `depends_on` con `condition: service_healthy`. Kubernetes non ha un equivalente diretto — la filosofia è "le app devono essere resilienti a dipendenze non pronte". In pratica però molti container falliscono al boot se Postgres non risponde subito.

Soluzione applicata: **initContainer** con `busybox` e `nc -z` che blocca finché il servizio non risponde sulla porta.

```yaml
initContainers:
  - name: wait-postgres
    image: busybox:1.36
    command: ["sh", "-c", "until nc -z postgres 5432; do sleep 2; done"]
```

Vantaggi:
- Il container principale parte solo dopo che le dipendenze sono raggiungibili.
- Se Postgres muore in seguito, il pod **non si riavvia** automaticamente — sta alla logica di retry dell'app riconnettersi. Questo è kubernetes-idiomatic: i pod vivono, la rete è eventually consistent.

---

## 9. Risorse (requests/limits)

Ho impostato:
- `requests`: il minimo che k8s "riserva" al pod (usato dallo scheduler).
- `limits`: il massimo oltre cui il pod viene throttled (CPU) o OOMKilled (memoria).

Valori conservativi, calibrati per VM da 4-8GB. Da aumentare se vedi `OOMKilled` o latenze alte.

OpenSearch è il più memory-hungry: `OPENSEARCH_JAVA_OPTS=-Xms512m -Xmx512m` per JVM, limit a 2Gi totali per il container (la JVM + buffer kernel + Lucene off-heap).

Postgres ha limit a 1Gi: sufficiente per il caso d'uso, ma se hai migrazioni pesanti o query complesse alzalo a 2-4Gi.

---

## 10. Naming: `mcp-server` e non `mcp_server`

I nomi dei **Service k8s** devono rispettare RFC 1035 (DNS): solo lowercase, cifre, `-`. Niente underscore.

Quindi i Service sono `mcp-server`, `email-poller`, `agent-worker`. Le **env var** restano con underscore (`MCP_SERVER_URL`) perché sono nomi POSIX, non DNS.

Nell'`01-configmap.yaml`:
```yaml
MCP_SERVER_URL: "http://mcp-server:8001/sse"
```
La variabile si chiama con underscore, il valore (l'hostname) con trattino. È coerente.

---

## 11. `VITE_API_URL`: build-time, non runtime

Il frontend è una SPA Vite. Le variabili `VITE_*` vengono **inline-ate nel bundle JavaScript a build-time** (`npm run build`). Non puoi cambiarle senza rebuild.

Implicazione: non puoi mettere `VITE_API_URL` in una ConfigMap — il frontend la ignorerebbe perché il valore è già "cottо" dentro `dist/assets/index-XXX.js`.

Quindi nel `22-frontend.yaml` **non c'è env per VITE_API_URL**. È un build-arg da passare al `docker build`:
```bash
docker build --build-arg VITE_API_URL=https://dms.example.com/api -t ... ./frontend
```

Se cambi dominio, devi ri-buildare e ri-deployare il frontend. Per render dinamico al runtime servirebbe sostituire Vite con SSR (Next.js, Nuxt) o iniettare la config via `window.__CONFIG__` da un file servito da nginx — out of scope.

---

## 12. `--reload` rimosso dal backend

Nel `docker-compose.yml` originale il backend gira con `uvicorn ... --reload`. È utile in sviluppo (hot reload sui file `.py`), **dannoso in produzione**:
- Tiene aperto un watcher su file system → consuma CPU e fd.
- Riavvia il processo a ogni modifica → in k8s i file non cambiano mai (immagine immutabile), quindi è morto codice.
- Disabilita certe ottimizzazioni di uvicorn.

Nel `21-backend.yaml`:
```yaml
command: ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```
Senza `--reload`. Per più worker in futuro, aggiungi `--workers 4` (ma considera prima `gunicorn` con worker class `uvicorn.workers.UvicornWorker`).

---

## 13. Ordine di apply

I file sono prefissati con numeri (`00-`, `10-`, `20-`, `30-`) per indicare l'ordine logico, **non** un requisito tecnico stretto. K8s in teoria riconcilia tutto da solo, ma in pratica:

1. `00-` → namespace (deve esistere prima di tutto).
2. `01-02` → ConfigMap + Secret (necessari per i pod).
3. `10-` → servizi stateful (Postgres, OpenSearch, SeaweedFS) — più lenti a partire, conviene avviarli prima.
4. `20-` → app (dipendono dai servizi sopra).
5. `30-40-` → ingress + cert-issuer (l'ingress fallisce se i Service backend non esistono).

Comando: `kubectl apply -f k8s/` applica tutto in ordine alfabetico — i prefissi numerici garantiscono l'ordine.

---

## 14. Cose che NON ho fatto (e perché)

- **HorizontalPodAutoscaler**: utile sotto carico, ma per un cluster a 3 nodi e workload del genere preferisci replica fissa e tuning manuale. Si aggiunge dopo, quando hai metriche reali.
- **NetworkPolicy**: traffic interno non ristretto. Per un setup didattico va bene; in produzione vera, restringi (es. solo backend può parlare con postgres).
- **PodDisruptionBudget**: rilevante quando hai più repliche e fai drain dei nodi. Con replica=1 non protegge nulla.
- **Resource Quota / LimitRange a livello namespace**: utile in cluster multi-tenant, qui è overkill.
- **Helm/Kustomize**: avrei potuto strutturare tutto come chart Helm o overlay Kustomize. Per il primo deploy, manifest raw sono più leggibili. Quando avrai ambienti multipli (dev/staging/prod), Kustomize è il passo successivo naturale.
- **Monitoring (Prometheus/Grafana)**: importante in produzione, l'ho lasciato fuori scope. Si installa con `kube-prometheus-stack` Helm chart.
- **Backup**: Longhorn ha snapshot/backup verso S3, ma vanno configurati (target backup + recurring job). Non l'ho automatizzato.

---

## TL;DR delle scelte

| Decisione | Scelta | Alternativa scartata |
|---|---|---|
| Distro k8s | k3s | kubeadm, GKE |
| Storage | Longhorn | local-path, NFS, Cloud SQL |
| Ingress | Traefik (default k3s) | ingress-nginx |
| TLS | cert-manager + Let's Encrypt | self-signed, Cloudflare |
| Secret management | Secret k8s + `.example` | SealedSecrets, External Secrets (futuro) |
| Stateful workloads | StatefulSet | Deployment con PVC |
| Service per StatefulSet | Headless | ClusterIP |
| Dipendenze inter-servizio | initContainer + `nc -z` | retry app-side puro |
| Hostname frontend/backend | unico, path-based | sottodomini + CORS |
| `VITE_API_URL` | build-arg | env runtime |
| Container registry | Artifact Registry GCP | Docker Hub, GHCR |
