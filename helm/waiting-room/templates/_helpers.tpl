{{- define "wr.fullname" -}}
{{- if contains .Chart.Name .Release.Name -}}{{ .Release.Name | trunc 50 | trimSuffix "-" }}
{{- else -}}{{ printf "%s-%s" .Release.Name .Chart.Name | trunc 50 | trimSuffix "-" }}{{- end -}}
{{- end }}

{{- define "wr.labels" -}}
app.kubernetes.io/name: {{ .Chart.Name }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version }}
{{- end }}

{{/* usage: include "wr.selector" (dict "root" . "component" "backend") */}}
{{- define "wr.selector" -}}
app.kubernetes.io/name: {{ .root.Chart.Name }}
app.kubernetes.io/instance: {{ .root.Release.Name }}
app.kubernetes.io/component: {{ .component }}
{{- end }}

{{- define "wr.backendImage" -}}
{{ .Values.image.registry }}/{{ .Values.backend.image.repository }}:{{ required "backend.image.tag is required (set to the git SHA)" .Values.backend.image.tag }}
{{- end }}

{{- define "wr.frontendImage" -}}
{{ .Values.image.registry }}/{{ .Values.frontend.image.repository }}:{{ required "frontend.image.tag is required (set to the git SHA)" .Values.frontend.image.tag }}
{{- end }}

{{- define "wr.dbEnv" -}}
- {name: DB_HOST, value: {{ include "wr.fullname" . }}-postgres}
- {name: DB_PORT, value: "5432"}
- {name: DB_NAME, value: {{ .Values.postgres.database | quote }}}
- {name: DB_USER, value: {{ .Values.postgres.username | quote }}}
- name: DB_PASSWORD
  valueFrom:
    secretKeyRef:
      name: {{ .Values.postgres.existingSecret }}
      key: {{ .Values.postgres.secretKey }}
{{- end }}
