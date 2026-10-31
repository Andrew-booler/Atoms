export class StudioOperation {
  private running = false;
  private retryAction: (() => Promise<void>) | null = null;

  constructor(private readonly onBusy: (value: boolean) => void,
    private readonly onError: (message: string | null) => void,
    private readonly describe: (error: unknown) => string) {}

  get busy() { return this.running; }
  get canRetry() { return this.retryAction !== null; }

  async run(action: () => Promise<void>) {
    if (this.running) return;
    this.running = true;
    this.retryAction = null;
    this.onBusy(true);
    this.onError(null);
    try {
      await action();
    } catch (error) {
      this.retryAction = action;
      this.onError(this.describe(error));
    } finally {
      this.running = false;
      this.onBusy(false);
    }
  }

  async retry() {
    const action = this.retryAction;
    if (action) await this.run(action);
  }
}
