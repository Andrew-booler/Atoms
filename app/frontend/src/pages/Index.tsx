import { Menu, X } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArtifactEditor } from '@/components/studio/ArtifactEditor';
import { ArtifactPreview } from '@/components/studio/ArtifactPreview';
import { BuildTerminal } from '@/components/studio/BuildTerminal';
import { ConversationStream } from '@/components/studio/ConversationStream';
import { ProjectRail } from '@/components/studio/ProjectRail';
import { RequirementComposer } from '@/components/studio/RequirementComposer';
import { useBuildTerminal } from '@/hooks/useBuildTerminal';
import { StudioOperation } from '@/lib/studio-operation';
import { describeError, studioApi, type BuildResponse, type ModelOption, type OutlinePayload, type PlanPayload, type ProjectDetail, type ProjectSummary, type StudioMessage, type VersionSummary } from '@/lib/studio';
import { cn } from '@/lib/utils';

const SUGGESTIONS = ['一个记录每日饮水量的追踪器，带进度环', '团队任务看板，支持新增、拖动状态、筛选', '个人记账本，按分类统计月度支出', '读书笔记库，支持标签和搜索'];
const planToText = (plan: PlanPayload) => [plan.summary, '', ...plan.steps.map((step, i) => `${i + 1}. ${step.title} — ${step.detail}`)].join('\n');

export default function StudioPage() {
  const navigate = useNavigate();
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [activeProject, setActiveProject] = useState<ProjectSummary | null>(null);
  const [messages, setMessages] = useState<StudioMessage[]>([]);
  const [versions, setVersions] = useState<VersionSummary[]>([]);
  const [artifactHtml, setArtifactHtml] = useState<string | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [activeVersion, setActiveVersion] = useState<number | null>(null);
  const [requirement, setRequirement] = useState('');
  const [revision, setRevision] = useState('');
  const [models, setModels] = useState<ModelOption[]>([]);
  const [profile, setProfile] = useState('balanced');
  const [busy, setBusy] = useState(false);
  const [stageLabel, setStageLabel] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [building, setBuilding] = useState(false);
  const [runningPlan, setRunningPlan] = useState<number | null>(null);
  const [editing, setEditing] = useState(false);
  const [mobileTab, setMobileTab] = useState<'chat' | 'preview'>('chat');
  const [drawer, setDrawer] = useState(false);
  const operation = useMemo(() => new StudioOperation(setBusy, setError, describeError), []);
  const terminal = useBuildTerminal();

  const updateSummary = (project: ProjectSummary) => {
    setActiveProject(project);
    setProjects(previous => [project, ...previous.filter(item => item.id !== project.id)]);
  };
  const applyDetail = (detail: ProjectDetail) => {
    updateSummary(detail.project);
    setMessages(detail.messages);
    setVersions(detail.versions);
    setArtifactHtml(detail.current_artifact ?? null);
    setPreviewUrl(null);
    setActiveVersion(detail.project.current_version ?? null);
    setEditing(false);
  };

  useEffect(() => {
    void operation.run(async () => {
      setStageLabel('正在读取共享项目与模拟配置…');
      try {
        setProjects(await studioApi.listProjects());
        const response = await studioApi.models();
        setModels(response.profiles);
        setProfile(response.default_profile);
      } finally { setStageLabel(''); }
    });
  }, [operation]);

  const startNewProject = () => {
    if (operation.busy) return;
    setActiveProject(null); setMessages([]); setVersions([]); setArtifactHtml(null); setPreviewUrl(null);
    setActiveVersion(null); setError(null); setMobileTab('chat'); setDrawer(false);
    terminal.reset();
  };
  const openProject = (project: ProjectSummary) => operation.run(async () => {
    setStageLabel('正在读取项目…');
    try {
      applyDetail(await studioApi.getProject(project.id));
      setDrawer(false);
      void terminal.loadLatest(project.id);
    }
    finally { setStageLabel(''); }
  });
  const removeProject = (project: ProjectSummary) => operation.run(async () => {
    setStageLabel('正在删除项目及历史记录…');
    try {
      await studioApi.deleteProject(project.id);
      setProjects(previous => previous.filter(item => item.id !== project.id));
      if (activeProject?.id === project.id) {
        setActiveProject(null); setMessages([]); setVersions([]); setArtifactHtml(null); setPreviewUrl(null); setActiveVersion(null);
        terminal.reset();
      }
    } finally { setStageLabel(''); }
  });

  const submitRequirement = () => {
    const text = requirement.trim();
    if (!text || operation.busy) return;
    const selectedProfile = profile;
    let project = activeProject;
    let savedMessage: StudioMessage | null = null;
    let creationAttempted = false;
    let creationBaseline: number[] | null = null;
    let messageAttempted = false;
    let messageBaseline: number[] | null = null;
    const clean = text.replace(/\s+/g, ' ');
    const projectName = clean.length > 24 ? `${clean.slice(0, 24)}…` : clean;
    void operation.run(async () => {
      setStageLabel('正在保存需求并取得模拟计划…');
      try {
        if (!project) {
          if (!creationBaseline) creationBaseline = (await studioApi.listProjects()).map(item => item.id);
          if (creationAttempted) {
            project = (await studioApi.listProjects()).find(item => !creationBaseline!.includes(item.id) && item.name === projectName && item.description === text) ?? null;
          }
          if (!project) {
            creationAttempted = true;
            project = await studioApi.createProject(projectName, text);
          }
          updateSummary(project);
        }
        if (!savedMessage) {
          if (!messageBaseline) messageBaseline = (await studioApi.getProject(project.id)).messages.map(item => item.id);
          if (messageAttempted) {
            savedMessage = (await studioApi.getProject(project.id)).messages.find(item => !messageBaseline!.includes(item.id) && item.role === 'user' && item.kind === 'requirement' && item.content === text) ?? null;
          }
          if (!savedMessage) {
            messageAttempted = true;
            savedMessage = await studioApi.appendMessage(project.id, { role: 'user', kind: 'requirement', content: text });
          }
          setMessages(previous => [...previous.filter(item => item.id !== savedMessage!.id), savedMessage!]);
          setRequirement('');
        }
        const buildId = await terminal.begin(project.id);
        terminal.watch(project.id, buildId);
        await studioApi.plan(project.id, text, selectedProfile, buildId);
        applyDetail(await studioApi.getProject(project.id));
      } finally { setStageLabel(''); }
    });
  };

  const approvePlan = (message: StudioMessage) => {
    const plan = message.meta.plan;
    const req = message.meta.requirement?.trim();
    if (operation.busy || !plan || !req || !activeProject || message.meta.approved) return;
    const projectId = activeProject.id;
    const selectedProfile = profile;
    let outline: OutlinePayload | null = null;
    let built: BuildResponse | null = null;
    void operation.run(async () => {
      setBuilding(true); setRunningPlan(message.id);
      try {
        if (!built) {
          const buildId = await terminal.begin(projectId);
          terminal.watch(projectId, buildId);
          setStageLabel('正在取得模拟页面结构…');
          if (!outline) outline = (await studioApi.outline(projectId, req, planToText(plan), selectedProfile, buildId)).outline;
          setStageLabel('正在保存模拟HTML与版本…');
          built = await studioApi.artifact(projectId, { requirement: req, plan_summary: planToText(plan), outline, profile: selectedProfile }, buildId);
        }
        updateSummary(built.project);
        setArtifactHtml(built.artifact_html); setPreviewUrl(built.preview_url ?? null); setActiveVersion(built.version.version_no);
        applyDetail(await studioApi.getProject(projectId));
        setMobileTab('preview');
      } finally { setBuilding(false); setRunningPlan(null); setStageLabel(''); }
    });
  };

  const restoreVersion = (version: VersionSummary) => {
    if (!activeProject || operation.busy || version.version_no === activeVersion) return;
    const projectId = activeProject.id;
    let restored = false;
    void operation.run(async () => {
      setStageLabel('正在恢复历史版本…');
      try {
        if (!restored) {
          const summary = await studioApi.restore(projectId, version.id);
          restored = true;
          updateSummary(summary); setActiveVersion(summary.current_version ?? null);
          // 已恢复但网页尚未读到，清除旧预览，避免把旧网页标为当前版。
          setArtifactHtml(null); setPreviewUrl(null);
        }
        const detail = await studioApi.getVersion(version.id);
        setArtifactHtml(detail.artifact_html); setPreviewUrl(null); setActiveVersion(detail.version_no);
        applyDetail(await studioApi.getProject(projectId));
      } catch (failure) {
        if (restored) throw new Error(`已恢复到v${version.version_no}，但读取页面失败；重试仅重新读取。${describeError(failure)}`);
        throw failure;
      } finally { setStageLabel(''); }
    });
  };

  const revisePlan = (message: StudioMessage) => {
    if (!operation.busy) { setRequirement(message.meta.requirement ?? ''); setMobileTab('chat'); }
  };

  const submitRevision = () => {
    const note = revision.trim();
    if (!note || operation.busy || !activeProject || activeVersion == null) return;
    const projectId = activeProject.id;
    const selectedProfile = profile;
    const baseVersion = versions.find(item => item.version_no === activeVersion);
    if (!baseVersion) return;
    let built: BuildResponse | null = null;
    let outline: OutlinePayload | null = null;
    void operation.run(async () => {
      setBuilding(true);
      try {
        if (!built) {
          const buildId = await terminal.begin(projectId);
          terminal.watch(projectId, buildId);
          setStageLabel('正在根据修改意见生成新版本…');
          if (!outline) outline = (await studioApi.outline(projectId, note, '', selectedProfile, buildId)).outline;
          built = await studioApi.artifact(projectId, {
            requirement: note,
            plan_summary: '',
            outline,
            profile: selectedProfile,
            base_version_id: baseVersion.id,
            revision_note: note,
          }, buildId);
        }
        updateSummary(built.project);
        setArtifactHtml(built.artifact_html); setPreviewUrl(built.preview_url ?? null); setActiveVersion(built.version.version_no);
        applyDetail(await studioApi.getProject(projectId));
        setRevision('');
        setMobileTab('preview');
      } finally { setBuilding(false); setStageLabel(''); }
    });
  };

  const submitEdit = (html: string, note: string) => {
    if (operation.busy || !activeProject) return;
    const projectId = activeProject.id;
    void operation.run(async () => {
      setBuilding(true);
      try {
        const buildId = await terminal.begin(projectId);
        terminal.watch(projectId, buildId);
        setStageLabel('正在保存编辑并重跑预览…');
        const built = await studioApi.editArtifact(projectId, { html, note }, buildId);
        updateSummary(built.project);
        setArtifactHtml(built.artifact_html);
        setPreviewUrl(built.preview_url ?? null);
        setActiveVersion(built.version.version_no);
        setEditing(false);
        applyDetail(await studioApi.getProject(projectId));
        setMobileTab('preview');
      } finally { setBuilding(false); setStageLabel(''); }
    });
  };

  const hasPendingPlan = messages.some(item => item.kind === 'plan' && !item.meta.approved);
  const rail = <ProjectRail projects={projects} activeId={activeProject?.id ?? null} loading={busy && projects.length === 0} busy={busy} activeNav="studio" onSelect={openProject} onCreate={startNewProject} onDelete={removeProject} onNavigate={target => { if (!operation.busy && target !== 'studio') navigate(`/${target}`); }} />;

  return <div className="flex h-screen overflow-hidden bg-paper">
    <div className="hidden w-[248px] shrink-0 md:block">{rail}</div>
    {drawer && <div className="fixed inset-0 z-40 flex bg-black/30 md:hidden"><div className="w-[280px] bg-paper"><button aria-label="关闭项目列表" disabled={busy} onClick={() => setDrawer(false)} className="m-2 p-2"><X /></button>{rail}</div></div>}
    <main className="flex min-w-0 flex-1 flex-col">
      <header className="flex h-14 shrink-0 items-center gap-3 border-b border-line px-4">
        <button aria-label="打开项目列表" disabled={busy} onClick={() => setDrawer(true)} className="p-2 md:hidden"><Menu size={18} /></button>
        <div className="min-w-0"><h1 className="truncate text-sm font-semibold text-ink">{activeProject?.name || '新的原型'}</h1><p className="mono text-[10.5px] text-ink-soft">{activeProject ? `v${activeProject.current_version ?? 0} · ${activeProject.version_count} 个版本` : '共享工作台 · 预置模拟输出'}</p></div>
        <div className="ml-auto flex gap-1 lg:hidden">{(['chat', 'preview'] as const).map(tab => <button key={tab} disabled={busy} onClick={() => setMobileTab(tab)} className={cn('rounded px-2 py-1 text-xs', mobileTab === tab ? 'bg-brand-soft text-brand-ink' : 'text-ink-soft')}>{tab === 'chat' ? '对话' : '预览'}</button>)}</div>
      </header>
      <div className="flex min-h-0 flex-1">
        <section aria-label="需求对话" className={cn('flex min-h-0 w-full flex-col lg:w-[46%] lg:border-r lg:border-line', mobileTab === 'preview' && 'hidden lg:flex')}>
          {messages.length === 0 && !busy && !error ? <div className="flex flex-1 flex-col justify-center px-6"><h2 className="text-[22px] font-semibold text-ink">描述需求，先看计划，<br />确认后查看固定预览。</h2><p className="mt-3 text-sm leading-7 text-ink-soft">本阶段使用预置模拟计划、结构和HTML，不调用真实模型。每次成功构建保存为独立历史版本。</p></div> : <ConversationStream messages={messages} planState={building ? 'running' : hasPendingPlan ? 'pending' : 'done'} runningPlanId={runningPlan} onApprove={approvePlan} onRevise={revisePlan} onRetry={operation.canRetry ? () => void operation.retry() : undefined} busy={busy} error={error} buildStage={stageLabel} onCopy={action => operation.run(action)} />}
          <BuildTerminal events={terminal.events} running={terminal.running} error={terminal.error} />
          {activeProject && activeVersion != null && (
            <div className="border-t border-line bg-paper px-4 py-2">
              <div className="mx-auto flex w-full max-w-[720px] items-center gap-2">
                <input
                  value={revision}
                  onChange={event => { if (!operation.busy) setRevision(event.target.value); }}
                  onKeyDown={event => { if (event.key === 'Enter' && !operation.busy && revision.trim()) submitRevision(); }}
                  placeholder="对当前成品提修改意见，例如：把标题改成红色"
                  aria-label="修改意见"
                  disabled={busy}
                  className="min-w-0 flex-1 rounded-md border border-line-strong bg-canvas px-3 py-2 text-[13px] leading-[1.5] text-ink placeholder:text-ink-faint outline-none transition-colors focus:border-ink-faint disabled:opacity-60"
                />
                <button
                  type="button"
                  onClick={submitRevision}
                  disabled={!revision.trim() || busy}
                  className="inline-flex h-9 shrink-0 items-center rounded-md bg-brand px-3 text-[12.5px] font-medium text-white transition-colors hover:bg-[#A93A0A] disabled:cursor-not-allowed disabled:opacity-50"
                >
                  生成新版本
                </button>
              </div>
            </div>
          )}
          <RequirementComposer value={requirement} onChange={value => { if (!operation.busy) setRequirement(value); }} onSubmit={submitRequirement} busy={busy} disabled={busy} placeholder={activeProject ? '继续输入，例如：增加备注' : '输入需求，例如：记录饮水'} models={models} profile={profile} onProfileChange={value => { if (!operation.busy) setProfile(value); }} suggestions={!messages.length ? SUGGESTIONS : []} hint="先取得模拟计划，确认后保存模拟HTML与版本。" />
        </section>
        <div className={cn('min-h-0 flex-1 lg:flex', mobileTab === 'preview' ? 'flex' : 'hidden')}>
          {editing && artifactHtml ? (
            <ArtifactEditor initialHtml={artifactHtml} busy={busy} onSave={submitEdit} onCancel={() => setEditing(false)} />
          ) : (
            <ArtifactPreview html={artifactHtml} previewUrl={previewUrl} title={activeProject?.name || '原型'} busy={busy} stageLabel={stageLabel} versions={versions} activeVersion={activeVersion} onRestore={restoreVersion} restoring={busy} onAction={action => operation.run(action)} onEdit={() => setEditing(true)} />
          )}
        </div>
      </div>
    </main>
  </div>;
}
