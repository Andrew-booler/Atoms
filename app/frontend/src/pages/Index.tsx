import { LogIn, X } from 'lucide-react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArtifactPreview } from '@/components/studio/ArtifactPreview';
import { ConversationStream } from '@/components/studio/ConversationStream';
import { ProjectRail } from '@/components/studio/ProjectRail';
import { RequirementComposer } from '@/components/studio/RequirementComposer';
import { useStudioAuth } from '@/hooks/useStudioAuth';
import {
  describeError,
  studioApi,
  type ModelOption,
  type PlanPayload,
  type ProjectSummary,
  type StudioMessage,
  type VersionSummary,
} from '@/lib/studio';
import { cn } from '@/lib/utils';

const SUGGESTIONS = [
  '一个记录每日饮水量的追踪器，带进度环',
  '团队任务看板，支持新增、拖动状态、筛选',
  '个人记账本，按分类统计月度支出',
  '读书笔记库，支持标签和搜索',
];

function projectNameFrom(requirement: string) {
  const clean = requirement.replace(/\s+/g, ' ').trim();
  return clean.length > 24 ? `${clean.slice(0, 24)}…` : clean || '未命名原型';
}

function planToText(plan: PlanPayload) {
  return [
    plan.summary,
    '',
    ...plan.steps.map((step, index) => `${index + 1}. ${step.title} — ${step.detail}`),
  ].join('\n');
}

type StageKey = 'plan' | 'outline' | 'artifact';

const STAGES: { key: StageKey; label: string }[] = [
  { key: 'plan', label: '计划' },
  { key: 'outline', label: '结构' },
  { key: 'artifact', label: '产物' },
];

function StageRail({ current, done }: { current: StageKey | null; done: boolean }) {
  const order: StageKey[] = ['plan', 'outline', 'artifact'];
  const currentIndex = current ? order.indexOf(current) : -1;

  return (
    <div className="flex items-center gap-1.5" aria-label="构建进度">
      {STAGES.map((stage, index) => {
        const isCurrent = current === stage.key;
        const isDone = done || (currentIndex > index && current !== null);
        return (
          <div key={stage.key} className="flex items-center gap-1.5">
            <span
              className={cn(
                'h-1.5 w-1.5 rounded-full',
                isCurrent && 'bg-brand stage-dot-active',
                !isCurrent && isDone && 'bg-ok',
                !isCurrent && !isDone && 'bg-line-strong'
              )}
            />
            <span
              className={cn(
                'mono text-[10px] uppercase tracking-[0.07em]',
                isCurrent ? 'text-brand-ink' : isDone ? 'text-ink-soft' : 'text-ink-faint'
              )}
            >
              {stage.label}
            </span>
            {index < STAGES.length - 1 && <span className="h-px w-3 bg-line-strong" />}
          </div>
        );
      })}
    </div>
  );
}

export default function StudioPage() {
  const navigate = useNavigate();
  const { state: authState, login, logout } = useStudioAuth();

  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [projectsLoading, setProjectsLoading] = useState(false);
  const [activeProject, setActiveProject] = useState<ProjectSummary | null>(null);

  const [messages, setMessages] = useState<StudioMessage[]>([]);
  const [versions, setVersions] = useState<VersionSummary[]>([]);
  const [artifactHtml, setArtifactHtml] = useState<string | null>(null);
  const [activeVersion, setActiveVersion] = useState<number | null>(null);

  const [requirement, setRequirement] = useState('');
  const [models, setModels] = useState<ModelOption[]>([]);
  const [profile, setProfile] = useState('balanced');

  const [planning, setPlanning] = useState(false);
  const [building, setBuilding] = useState(false);
  const [stageLabel, setStageLabel] = useState('');
  const [stage, setStage] = useState<StageKey | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [restoring, setRestoring] = useState(false);
  const [loginNotice, setLoginNotice] = useState(false);
  const [mobileTab, setMobileTab] = useState<'chat' | 'preview'>('chat');

  const busy = planning || building;
  const isAuthed = authState === 'authenticated';

  const loadProjects = useCallback(async () => {
    setProjectsLoading(true);
    try {
      const list = await studioApi.listProjects();
      setProjects(list);
      setActiveProject((prev) => (prev ? list.find((item) => item.id === prev.id) ?? prev : prev));
    } catch (err) {
      setError(describeError(err));
    } finally {
      setProjectsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!isAuthed) {
      setProjects([]);
      return;
    }
    loadProjects();
    studioApi
      .models()
      .then((res) => {
        setModels(res.profiles);
        setProfile(res.default_profile);
      })
      .catch(() => setModels([]));
  }, [isAuthed, loadProjects]);

  const openProject = useCallback(async (project: ProjectSummary) => {
    setError(null);
    setActiveProject(project);
    try {
      const detail = await studioApi.getProject(project.id);
      setMessages(detail.messages);
      setVersions(detail.versions);
      setArtifactHtml(detail.current_artifact ?? null);
      setActiveVersion(detail.project.current_version ?? null);
      setActiveProject(detail.project);
    } catch (err) {
      setError(describeError(err));
    }
  }, []);

  const startNewProject = () => {
    setActiveProject(null);
    setMessages([]);
    setVersions([]);
    setArtifactHtml(null);
    setActiveVersion(null);
    setError(null);
    setMobileTab('chat');
  };

  const removeProject = async (project: ProjectSummary) => {
    try {
      await studioApi.deleteProject(project.id);
      setProjects((prev) => prev.filter((item) => item.id !== project.id));
      if (activeProject?.id === project.id) startNewProject();
    } catch (err) {
      setError(describeError(err));
    }
  };

  const submitRequirement = async () => {
    const text = requirement.trim();
    if (!text || busy) return;
    if (!isAuthed) {
      setLoginNotice(true);
      return;
    }

    setError(null);
    setLoginNotice(false);
    setPlanning(true);
    setStage('plan');
    setStageLabel('正在拆解需求，生成执行计划…');

    try {
      let project = activeProject;
      if (!project) {
        project = await studioApi.createProject(projectNameFrom(text), text);
        setActiveProject(project);
        setProjects((prev) => [project as ProjectSummary, ...prev]);
      }

      const userMessage = await studioApi.appendMessage(project.id, {
        role: 'user',
        kind: 'requirement',
        content: text,
      });
      setMessages((prev) => [...prev, userMessage]);
      setRequirement('');

      const res = await studioApi.plan(project.id, text, profile);
      setMessages((prev) => [...prev, res.message]);
      setStage(null);
    } catch (err) {
      setError(describeError(err));
      setStage(null);
    } finally {
      setPlanning(false);
      setStageLabel('');
    }
  };

  const approvePlan = async (message: StudioMessage) => {
    const plan = message.meta.plan;
    const req = message.meta.requirement?.trim();
    if (!plan || !req || !activeProject || busy) return;

    setError(null);
    setBuilding(true);
    setStage('outline');
    setStageLabel('正在设计界面结构与示例数据…');

    try {
      const outlineRes = await studioApi.outline(activeProject.id, req, planToText(plan), profile);
      setStage('artifact');
      setStageLabel('正在构建可运行成品…');

      const buildRes = await studioApi.artifact(activeProject.id, {
        requirement: req,
        plan_summary: planToText(plan),
        outline: outlineRes.outline,
        profile,
      });

      setMessages((prev) => [
        ...prev.map((item) =>
          item.id === message.id ? { ...item, meta: { ...item.meta, approved: true } } : item
        ),
        buildRes.message,
      ]);
      setArtifactHtml(buildRes.artifact_html);
      setActiveVersion(buildRes.version.version_no);
      setVersions((prev) => [buildRes.version, ...prev]);
      setActiveProject(buildRes.project);
      setProjects((prev) =>
        prev.map((item) => (item.id === buildRes.project.id ? buildRes.project : item))
      );
      setMobileTab('preview');
    } catch (err) {
      setError(describeError(err));
    } finally {
      setBuilding(false);
      setStage(null);
      setStageLabel('');
    }
  };

  const restoreVersion = async (version: VersionSummary) => {
    if (!activeProject || restoring || busy) return;
    setRestoring(true);
    setError(null);
    try {
      await studioApi.restore(activeProject.id, version.id);
      const detail = await studioApi.getVersion(version.id);
      setArtifactHtml(detail.artifact_html);
      setActiveVersion(detail.version_no);
      setMessages((prev) => [
        ...prev,
        {
          id: Date.now(),
          role: 'system',
          kind: 'note',
          content: `已回滚到 v${detail.version_no}。`,
          meta: {},
        },
      ]);
    } catch (err) {
      setError(describeError(err));
    } finally {
      setRestoring(false);
    }
  };

  const lastUserRequirement = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i -= 1) {
      if (messages[i].role === 'user') return messages[i].content;
    }
    return '';
  }, [messages]);

  const revisePlan = () => {
    setRequirement(lastUserRequirement);
  };

  const hasPendingPlan = messages.some(
    (item) => item.kind === 'plan' && item.meta.approved !== true
  );
  const planState: 'pending' | 'running' | 'done' = building
    ? 'running'
    : hasPendingPlan
      ? 'pending'
      : 'done';

  return (
    <div className="flex h-screen overflow-hidden bg-paper">
      <div className="hidden w-[248px] shrink-0 md:block">
        <ProjectRail
          projects={projects}
          activeId={activeProject?.id ?? null}
          loading={projectsLoading}
          authState={authState}
          activeNav="studio"
          onSelect={openProject}
          onCreate={startNewProject}
          onDelete={removeProject}
          onNavigate={(target) => navigate(target === 'studio' ? '/' : `/${target}`)}
          onLogin={login}
          onLogout={async () => {
            setProjects([]);
            startNewProject();
            await logout();
          }}
        />
      </div>

      <main className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 shrink-0 items-center gap-3 border-b border-line px-4">
          <div className="min-w-0">
            <h1 className="truncate text-[14px] font-semibold leading-5 tracking-[-0.01em] text-ink">
              {activeProject?.name || '新的原型'}
            </h1>
            <p className="mono truncate text-[10.5px] leading-4 text-ink-faint">
              {activeProject
                ? `v${activeProject.current_version ?? 0} · ${activeProject.version_count} 个版本`
                : '输入需求以创建项目'}
            </p>
          </div>

          <div className="ml-auto flex items-center gap-3">
            <StageRail current={stage} done={!!artifactHtml && !busy && !hasPendingPlan} />
            <span className="hidden h-4 w-px bg-line sm:block" />
            <div className="flex items-center gap-1 rounded-md border border-line bg-canvas p-0.5 lg:hidden">
              <button
                type="button"
                onClick={() => setMobileTab('chat')}
                className={cn(
                  'h-6 rounded px-2 text-[11.5px] transition-colors',
                  mobileTab === 'chat' ? 'bg-paper text-ink' : 'text-ink-faint'
                )}
              >
                对话
              </button>
              <button
                type="button"
                onClick={() => setMobileTab('preview')}
                className={cn(
                  'h-6 rounded px-2 text-[11.5px] transition-colors',
                  mobileTab === 'preview' ? 'bg-paper text-ink' : 'text-ink-faint'
                )}
              >
                预览
              </button>
            </div>
          </div>
        </header>

        <div className="flex min-h-0 flex-1">
          <section
            className={cn(
              'flex min-h-0 w-full min-w-0 flex-col border-line lg:w-[46%] lg:border-r',
              mobileTab === 'preview' && 'hidden lg:flex'
            )}
            aria-label="需求对话"
          >
            {messages.length === 0 && !busy ? (
              <div className="studio-scroll flex min-h-0 flex-1 flex-col justify-center overflow-y-auto px-6 py-8">
                <div className="mx-auto w-full max-w-[720px]">
                  <span className="mono text-[10.5px] uppercase tracking-[0.12em] text-brand">
                    原型化开发
                  </span>
                  <h2 className="mt-2 text-[22px] font-semibold leading-[1.3] tracking-[-0.02em] text-ink">
                    描述一个应用，先看计划，
                    <br />
                    再在右侧直接操作成品。
                  </h2>
                  <p className="mt-2.5 max-w-[520px] text-[13.5px] leading-[1.7] text-ink-soft">
                    AI 会先把需求拆成可确认的执行计划，确认后真实生成可运行的前端应用，并保存为可回滚的版本。
                  </p>

                  <dl className="mt-5 grid gap-x-6 gap-y-3 border-t border-line pt-4 sm:grid-cols-3">
                    {[
                      { term: '计划模式', desc: '先审计划，确认后才执行' },
                      { term: '实时预览', desc: '产物在沙箱内直接交互' },
                      { term: '版本可回溯', desc: '每次构建都能回滚' },
                    ].map((item) => (
                      <div key={item.term}>
                        <dt className="text-[12.5px] font-medium text-ink">{item.term}</dt>
                        <dd className="mt-0.5 text-[12px] leading-[1.55] text-ink-faint">
                          {item.desc}
                        </dd>
                      </div>
                    ))}
                  </dl>
                </div>
              </div>
            ) : (
              <ConversationStream
                messages={messages}
                planState={planState}
                onApprove={approvePlan}
                onRevise={revisePlan}
                onRetry={() => setError(null)}
                busy={busy}
                error={error}
                buildStage={stageLabel}
              />
            )}

            {loginNotice && !isAuthed && (
              <div className="border-t border-line bg-brand-soft px-4 py-2.5">
                <div className="mx-auto flex w-full max-w-[720px] items-center gap-2">
                  <LogIn className="h-3.5 w-3.5 shrink-0 text-brand-ink" strokeWidth={2} />
                  <p className="min-w-0 flex-1 text-[12.5px] text-brand-ink">
                    登录后即可保存项目、版本与预览产物。
                  </p>
                  <button
                    type="button"
                    onClick={login}
                    className="inline-flex h-7 items-center rounded bg-brand px-2.5 text-[12px] font-medium text-white transition-colors hover:bg-[#A93A0A]"
                  >
                    去登录
                  </button>
                  <button
                    type="button"
                    onClick={() => setLoginNotice(false)}
                    aria-label="关闭提示"
                    className="flex h-7 w-7 items-center justify-center rounded text-brand-ink/70 hover:text-brand-ink"
                  >
                    <X className="h-3.5 w-3.5" strokeWidth={2} />
                  </button>
                </div>
              </div>
            )}

            {error && messages.length === 0 && (
              <div role="alert" className="border-t border-line px-4 py-2">
                <p className="mx-auto w-full max-w-[720px] text-[12.5px] text-err">{error}</p>
              </div>
            )}

            <RequirementComposer
              value={requirement}
              onChange={setRequirement}
              onSubmit={submitRequirement}
              busy={busy}
              disabled={building}
              placeholder={
                activeProject
                  ? '继续描述要新增或修改的功能，例如「加上按月筛选」…'
                  : '例如：做一个记录每日饮水量的追踪器，带进度环和打卡历史…'
              }
              models={models}
              profile={profile}
              onProfileChange={setProfile}
              suggestions={messages.length === 0 ? SUGGESTIONS : []}
              hint={
                building
                  ? '正在按确认的计划构建，完成后预览会自动更新。'
                  : '先生成计划，确认后才会真正构建成品。'
              }
            />
          </section>

          <div
            className={cn(
              'min-h-0 flex-1 lg:flex',
              mobileTab === 'preview' ? 'flex' : 'hidden'
            )}
          >
            <ArtifactPreview
              html={artifactHtml}
              title={activeProject?.name || '原型'}
              busy={busy}
              stageLabel={stageLabel}
              versions={versions}
              activeVersion={activeVersion}
              onRestore={restoreVersion}
              restoring={restoring}
            />
          </div>
        </div>
      </main>
    </div>
  );
}
