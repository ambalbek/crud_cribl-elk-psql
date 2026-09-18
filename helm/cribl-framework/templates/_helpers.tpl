{{/*
Standard labels for a component. Call with:
  include "cf.labels" (dict "root" $ "name" "<component>")
*/}}
{{- define "cf.labels" -}}
helm.sh/chart: {{ printf "%s-%s" .root.Chart.Name .root.Chart.Version | trunc 63 | trimSuffix "-" }}
app.kubernetes.io/name: {{ .name }}
app.kubernetes.io/instance: {{ .root.Release.Name }}
app.kubernetes.io/version: {{ .root.Chart.AppVersion | quote }}
app.kubernetes.io/part-of: cribl-framework
app.kubernetes.io/managed-by: {{ .root.Release.Service }}
{{- end }}

{{/* Immutable selector labels. Call with the same dict as cf.labels. */}}
{{- define "cf.selectorLabels" -}}
app.kubernetes.io/name: {{ .name }}
app.kubernetes.io/instance: {{ .root.Release.Name }}
{{- end }}

{{/* Image reference — digest wins over tag. Call with (dict "image" .Values.<c>.image) */}}
{{- define "cf.image" -}}
{{- if .image.digest -}}
{{ .image.repository }}@{{ .image.digest }}
{{- else -}}
{{ .image.repository }}:{{ .image.tag }}
{{- end -}}
{{- end }}

{{- define "cf.serviceAccountName" -}}
{{- if .Values.serviceAccount.create -}}
{{ .Values.serviceAccount.name | default (printf "%s-cribl-framework" .Release.Name) }}
{{- else -}}
{{ .Values.serviceAccount.name | default "default" }}
{{- end -}}
{{- end }}

{{/*
Common pod-spec fields shared by every workload. Call with $.
Emits at the indentation of a pod spec's direct children (indented by caller).
*/}}
{{- define "cf.podCommon" -}}
{{- with .Values.global.imagePullSecrets }}
imagePullSecrets:
  {{- toYaml . | nindent 2 }}
{{- end }}
serviceAccountName: {{ include "cf.serviceAccountName" . }}
automountServiceAccountToken: false
{{- with .Values.global.priorityClassName }}
priorityClassName: {{ . }}
{{- end }}
securityContext:
  {{- toYaml .Values.global.podSecurityContext | nindent 2 }}
{{- end }}

{{/*
Scheduling fields for a component. Call with (dict "comp" .Values.<component>)
*/}}
{{- define "cf.podScheduling" -}}
{{- with .comp.nodeSelector }}
nodeSelector:
  {{- toYaml . | nindent 2 }}
{{- end }}
{{- with .comp.tolerations }}
tolerations:
  {{- toYaml . | nindent 2 }}
{{- end }}
{{- with .comp.affinity }}
affinity:
  {{- toYaml . | nindent 2 }}
{{- end }}
{{- with .comp.topologySpreadConstraints }}
topologySpreadConstraints:
  {{- toYaml . | nindent 2 }}
{{- end }}
{{- end }}

{{/* extraEnv map rendered as env entries. Call with (dict "extra" <map>) */}}
{{- define "cf.extraEnv" -}}
{{- range $key, $value := .extra }}
- name: {{ $key }}
  value: {{ $value | quote }}
{{- end }}
{{- end }}

{{/* Internal service URLs (only rendered when the component is enabled). */}}
{{- define "cf.criblServiceUrl" -}}
http://{{ .Release.Name }}-cribl-service:8001
{{- end }}

{{- define "cf.eceServiceUrl" -}}
http://{{ .Release.Name }}-ece-service:8002
{{- end }}

{{- define "cf.etnOnboardingUrl" -}}
http://{{ .Release.Name }}-etn-onboarding:5000
{{- end }}

{{/* AUTH_LOCAL_USERS for etn_onboarding — kept in sync with the framework token. */}}
{{- define "cf.etnAuthLocalUsers" -}}
{{- if .Values.etnOnboarding.authLocalUsers -}}
{{- .Values.etnOnboarding.authLocalUsers -}}
{{- else -}}
[{"username":"framework","token":"{{ .Values.framework.etnOnboardingToken }}","roles":["platform_admin"]}]
{{- end -}}
{{- end }}
