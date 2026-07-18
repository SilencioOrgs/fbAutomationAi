import { EventEmitter } from 'events';

class PipelineEventBus extends EventEmitter {
  constructor() {
    super();
    // Increase max listeners since SSE clients might attach many
    this.setMaxListeners(50);
  }
}

// Singleton instance
const eventBus = new PipelineEventBus();

export default eventBus;
