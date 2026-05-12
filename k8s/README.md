# Deploy DMS su k3s (GCP, 3 VM)

Guida step-by-step per portare il progetto su un cluster k3s con 1 master + 2 worker.

## Prerequisiti sulle VM (tutte e 3)

```bash
# disabilita swap
sudo swapoff -a
sudo sed -i '/ swap / s/^/#/' /etc/fstab

# sysctl per OpenSearch (solo sui worker, ma metterlo ovunque non fa danni)
echo 'vm.max_map_count=262144' | sudo tee /etc/sysctl.d/99-opensearch.conf
sudo sysctl --system

# open-iscsi per Longhorn
sudo apt-get update
sudo apt-get install -y open-iscsi nfs-common
sudo systemctl enable --now iscsid
```

## 1. Firewall GCP

Regola in VPC che permetta tra le 3 VM (source = tag/network interna):
- `tcp:6443,10250,2379-2380`
- `udp:8472` (flannel VXLAN)

Verso Internet, solo sul nodo che esponi pubblicamente:
- `tcp:80,443`

## 2. Installazione k3s

**Master:**
```bash
curl -sfL https://get.k3s.io | INSTALL_K3S_EXEC="server --write-kubeconfig-mode 644 --tls-san=<IP_PUBBLICO_MASTER>" sh -
sudo cat /var/lib/rancher/k3s/server/node-token
```

**Worker (entrambi):**
```bash
curl -sfL https://get.k3s.io | K3S_URL=https://<IP_INTERNO_MASTER>:6443 K3S_TOKEN=<token> sh -
```

**Da client locale:**
```bash
scp <user>@<MASTER>:/etc/rancher/k3s/k3s.yaml ~/.kube/config-dms
sed -i "s/127.0.0.1/<IP_PUBBLICO_MASTER>/" ~/.kube/config-dms
export KUBECONFIG=~/.kube/config-dms
kubectl get nodes   # devono comparire tutti e 3
```

## 3. Longhorn (storage)

```bash
kubectl apply -f https://raw.githubusercontent.com/longhorn/longhorn/v1.7.2/deploy/longhorn.yaml
kubectl -n longhorn-system get pods -w   # attendi che tutto sia Running
kubectl patch storageclass longhorn -p '{"metadata":{"annotations":{"storageclass.kubernetes.io/is-default-class":"true"}}}'
```

UI (opzionale, port-forward):
```bash
kubectl -n longhorn-system port-forward svc/longhorn-frontend 8888:80
```

## 4. cert-manager

```bash
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.16.1/cert-manager.yaml
kubectl -n cert-manager wait --for=condition=Available deploy --all --timeout=300s
```

## 5. Build & push immagini

Scegli un registry (Artifact Registry GCP consigliato):

```bash
gcloud artifacts repositories create dms --location=europe-west1 --repository-format=docker
gcloud auth configure-docker europe-west1-docker.pkg.dev

REGISTRY=europe-west1-docker.pkg.dev/<PROJECT_ID>/dms
TAG=$(git rev-parse --short HEAD)

docker build -t $REGISTRY/dms-backend:$TAG ./backend
docker build -t $REGISTRY/dms-mcp-server:$TAG ./mcp_server
docker build -t $REGISTRY/dms-email-poller:$TAG ./email_poller
docker build -t $REGISTRY/dms-agent-worker:$TAG ./agent_worker
docker build --build-arg VITE_API_URL=https://dms.example.com/api -t $REGISTRY/dms-frontend:$TAG ./frontend

for img in backend mcp-server email-poller agent-worker frontend; do
  docker push $REGISTRY/dms-$img:$TAG
done
```

Poi sostituisci `REGISTRY/dms-*:TAG` nei file `20-` `21-` `22-` `23-` `24-` con i tag reali (o usa `sed`/Kustomize).

Per autenticazione del cluster al registry:
```bash
kubectl -n dms create secret docker-registry gcr-pull \
  --docker-server=europe-west1-docker.pkg.dev \
  --docker-username=_json_key \
  --docker-password="$(cat key.json)" \
  --docker-email=stefanoallevi01@gmail.com
```
Poi aggiungi `imagePullSecrets: [{name: gcr-pull}]` nei pod template (o nel default service account del namespace).

## 6. ConfigMap da file (init.sql, s3.json)

```bash
kubectl -n dms create configmap postgres-init-sql --from-file=init.sql=./init.sql
kubectl -n dms create configmap seaweedfs-s3-config --from-file=s3.json=./s3.json
```

## 7. Secret

```bash
cp k8s/02-secret.example.yaml k8s/02-secret.yaml
# edita 02-secret.yaml con i valori reali
kubectl apply -f k8s/02-secret.yaml
# poi NON committarlo (aggiungilo a .gitignore)
```

## 8. Apply in ordine

```bash
kubectl apply -f k8s/00-namespace.yaml
kubectl apply -f k8s/01-configmap.yaml
kubectl apply -f k8s/02-secret.yaml
kubectl apply -f k8s/10-postgres.yaml
kubectl apply -f k8s/11-opensearch.yaml
kubectl apply -f k8s/12-seaweedfs-master.yaml
kubectl apply -f k8s/13-seaweedfs-volume.yaml
kubectl apply -f k8s/14-seaweedfs-filer.yaml
kubectl apply -f k8s/15-seaweedfs-s3.yaml
kubectl apply -f k8s/16-tika.yaml
kubectl apply -f k8s/20-mcp-server.yaml
kubectl apply -f k8s/21-backend.yaml
kubectl apply -f k8s/22-frontend.yaml
kubectl apply -f k8s/23-email-poller.yaml
kubectl apply -f k8s/24-agent-worker.yaml
kubectl apply -f k8s/40-cert-issuer.yaml
kubectl apply -f k8s/30-ingress.yaml
```

Verifica:
```bash
kubectl -n dms get pods
kubectl -n dms get pvc
kubectl -n dms get ingress
```

## 9. DNS

Punta `dms.example.com` all'IP pubblico del master (o all'IP di un LB GCP TCP che bilancia 80/443 sulle 3 VM). cert-manager risolverà la sfida HTTP-01 e otterrà il certificato automaticamente.

## Cose da modificare nel codice

1. **backend**: togli `--reload` (già fatto nel manifest, il `command` non lo passa più).
2. **frontend**: l'`VITE_API_URL` deve diventare `https://<dominio>/api` a build-time.
3. **backend routing**: assicurati che le API siano servite sotto `/api`, oppure aggiungi un middleware Traefik `StripPrefix` con annotation sull'Ingress.

## Troubleshooting comune

| Sintomo | Causa probabile |
|---|---|
| OpenSearch in CrashLoop con "max virtual memory areas..." | `vm.max_map_count` non impostato sul nodo |
| PVC `Pending` da minuti | Longhorn non pronto / `open-iscsi` non installato su un nodo |
| Ingress con `404` da Traefik | DNS non punta al nodo giusto, o `host:` nell'ingress non corrisponde |
| Certificato non emesso | cert-manager non vede l'Ingress sulla porta 80 → controlla firewall e DNS |
| Pod `ImagePullBackOff` | manca `imagePullSecrets` o il tag non esiste nel registry |
