// RevisionReport.tsx — 修订报告面板

import { cn } from '@/lib/utils'
import { CheckCircle2, AlertTriangle, XCircle, Info, BookOpen } from 'lucide-react'

/** Revision issue severity */
export type IssueSeverity = 'critical' | 'warning' | 'info' | 'suggestion'

/** Single revision issue */
export interface RevisionIssue {
  severity: IssueSeverity
  description: string
  suggestion?: string
  chapterNumber?: number
  volumeNumber?: number
}

/** Modification made during revision */
export interface RevisionModification {
  chapter: number
  location: string
  change: string
}

interface RevisionReportProps {
  revisionContext: 'per_volume' | 'full_book'
  volumeNumber?: number
  totalVolumes?: number
  issues: RevisionIssue[]
  modifications?: RevisionModification[]
  isProcessing?: boolean
}

const SEVERITY_CONFIG: Record<IssueSeverity, { icon: typeof XCircle; color: string; label: string }> = {
  critical: { icon: XCircle, color: 'text-red-600', label: '🔴' },
  warning: { icon: AlertTriangle, color: 'text-amber-600', label: '🟠' },
  info: { icon: Info, color: 'text-blue-600', label: '🟡' },
  suggestion: { icon: CheckCircle2, color: 'text-green-600', label: '🟢' },
}

export function RevisionReport({
  revisionContext,
  volumeNumber,
  totalVolumes,
  issues,
  modifications = [],
  isProcessing = false,
}: RevisionReportProps) {
  const scope = revisionContext === 'per_volume'
    ? `第${volumeNumber}卷逐卷修订`
    : `全书修订（${totalVolumes || '?'}卷）`

  // Count issues by severity
  const counts = issues.reduce(
    (acc, i) => { acc[i.severity] = (acc[i.severity] || 0) + 1; return acc },
    {} as Record<IssueSeverity, number>
  )

  return (
    <div className="space-y-3">
      {/* Header */}
      <div className="flex items-center gap-2">
        <BookOpen className="h-4 w-4 text-primary" />
        <span className="text-sm font-medium">{scope}</span>
        {isProcessing && (
          <span className="text-[10px] bg-primary/10 text-primary px-1.5 py-0.5 rounded animate-pulse">
            修订中...
          </span>
        )}
      </div>

      {/* Severity summary */}
      {issues.length > 0 && (
        <div className="flex items-center gap-3 text-[11px]">
          {(Object.entries(counts) as [IssueSeverity, number][]).map(([sev, count]) => {
            const cfg = SEVERITY_CONFIG[sev]
            return (
              <span key={sev} className={cn('flex items-center gap-1', cfg.color)}>
                {cfg.label} {count}
              </span>
            )
          })}
        </div>
      )}

      {/* Issues list */}
      <div className="space-y-1.5 max-h-[300px] overflow-y-auto">
        {issues.length === 0 && !isProcessing && (
          <div className="text-[11px] text-muted-foreground py-2">
            未发现问题
          </div>
        )}

        {issues.map((issue, idx) => {
          const cfg = SEVERITY_CONFIG[issue.severity]
          const Icon = cfg.icon
          return (
            <div
              key={idx}
              className={cn(
                'rounded-md border px-2.5 py-2 text-[11px]',
                issue.severity === 'critical' && 'border-red-200 bg-red-50',
                issue.severity === 'warning' && 'border-amber-200 bg-amber-50',
                issue.severity === 'info' && 'border-blue-200 bg-blue-50',
                issue.severity === 'suggestion' && 'border-green-200 bg-green-50',
              )}
            >
              <div className="flex items-start gap-1.5">
                <Icon className={cn('h-3.5 w-3.5 flex-shrink-0 mt-0.5', cfg.color)} />
                <div className="flex-1 min-w-0">
                  <div className="text-[11px]">
                    {issue.volumeNumber && (
                      <span className="text-muted-foreground mr-1">
                        第{issue.volumeNumber}卷
                      </span>
                    )}
                    {issue.chapterNumber && (
                      <span className="text-muted-foreground mr-1">
                        第{issue.chapterNumber}章
                      </span>
                    )}
                    {issue.description}
                  </div>
                  {issue.suggestion && (
                    <div className="text-[10px] text-muted-foreground mt-0.5">
                      建议：{issue.suggestion}
                    </div>
                  )}
                </div>
              </div>
            </div>
          )
        })}
      </div>

      {/* Modifications list */}
      {modifications.length > 0 && (
        <div className="space-y-1">
          <div className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
            修改记录
          </div>
          {modifications.map((mod, idx) => (
            <div
              key={idx}
              className="text-[11px] bg-muted/50 rounded px-2 py-1.5"
            >
              <span className="text-muted-foreground">第{mod.chapter}章 · {mod.location}</span>
              <div className="mt-0.5">{mod.change}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
