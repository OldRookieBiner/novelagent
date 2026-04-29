// frontend/src/pages/Writing.tsx
import { useParams, useNavigate } from 'react-router-dom'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import ErrorMessage from '@/components/common/ErrorMessage'
import StepNavigation from '@/components/project/StepNavigation'
import { useWriting } from '@/components/writing/hooks/useWriting'
import ChapterNav from '@/components/writing/ChapterNav'
import ChapterEditor from '@/components/writing/ChapterEditor'

export default function Writing()
{
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const {
    project,
    chapterOutlines,
    currentChapter,
    content,
    isGenerating,
    isSaving,
    wordCount,
    error,
    loading,
    mode,
    handleChapterSelect,
    handleGenerate,
    handleStop,
    handleSave,
    handleContentChange,
    setMode,
    clearError,
  } = useWriting(id)

  if (loading)
  {
    return (
      <div className="flex items-center justify-center py-20">
        <LoadingSpinner text="加载中..." />
      </div>
    )
  }

  if (!project || !currentChapter)
  {
    return (
      <div className="max-w-4xl mx-auto">
        <ErrorMessage message="项目或章节不存在" />
      </div>
    )
  }

  return (
    <div>
      {/* 步骤导航 */}
      <StepNavigation
        currentStage={project.workflow_state?.stage || 'inspiration'}
        viewingStep={null}
        onViewStep={(stepIndex) => navigate(`/project/${id}?viewStep=${stepIndex}`)}
      />

      <div className="flex min-h-[calc(100vh-80px)]">
        {/* 左侧章节导航 */}
        <ChapterNav
          chapterOutlines={chapterOutlines}
          currentChapter={currentChapter}
          isGenerating={isGenerating}
          onSelectChapter={handleChapterSelect}
        />

        {/* 右侧编辑器 */}
        <ChapterEditor
          projectId={id!}
          chapterNumber={currentChapter.chapter_number}
          chapterTitle={currentChapter.title || ''}
          chapterOutline={{
            scene: currentChapter.scene,
            characters: currentChapter.characters,
            plot: currentChapter.plot,
            conflict: currentChapter.conflict,
            ending: currentChapter.ending,
          }}
          content={content}
          wordCount={wordCount}
          mode={mode}
          isGenerating={isGenerating}
          isSaving={isSaving}
          error={error}
          onGenerate={handleGenerate}
          onStop={handleStop}
          onSave={handleSave}
          onContentChange={handleContentChange}
          onModeChange={setMode}
          onClearError={clearError}
        />
      </div>
    </div>
  )
}
