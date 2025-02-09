import { ApolloClient, InMemoryCache, split, HttpLink } from '@apollo/client';
import { WebSocketLink } from '@apollo/client/link/ws';
import { getMainDefinition } from '@apollo/client/utilities';
import { gql } from '@apollo/client';
import { Viewer } from '@speckle/viewer';
import { SpeckleLoader } from '@speckle/viewer';

export class SpeckleSubscriptionManager {
    constructor(serverUrl, token, viewer) {
        this.viewer = viewer;
        this.serverUrl = serverUrl;
        this.subscription = null;
        this.token = token;
        this.currentObjectUrl = null;
        this.currentStreamId = null;

        // Setup Apollo Client
        const httpLink = new HttpLink({
            uri: `${serverUrl}/graphql`,
            headers: { Authorization: `Bearer ${token}` }
        });

        const wsLink = new WebSocketLink({
            uri: `${serverUrl.replace('http', 'ws')}/graphql`,
            options: {
                reconnect: true,
                connectionParams: { Authorization: `Bearer ${token}` }
            }
        });

        const splitLink = split(
            ({ query }) => {
                const definition = getMainDefinition(query);
                return definition.kind === 'OperationDefinition' &&
                       definition.operation === 'subscription';
            },
            wsLink,
            httpLink
        );

        this.client = new ApolloClient({
            link: splitLink,
            cache: new InMemoryCache()
        });
    }

    startSubscription(streamId, initialObjectId) {
        this.currentStreamId = streamId;
        this.currentObjectUrl = this.getObjectUrl(streamId, initialObjectId);

        const SUBSCRIPTION = gql`
            subscription OnStreamUpdated($streamId: String!) {
                commitCreated(streamId: $streamId)
            }
        `;

        this.subscription = this.client.subscribe({
            query: SUBSCRIPTION,
            variables: { streamId }
        }).subscribe({
            next: async ({ data }) => {
                console.log('Received new commit:', data);
                if (data?.commitCreated) {
                    const commitData = data.commitCreated;
                    await this.reloadViewer(streamId, commitData);
                }
            },
            error: (error) => {
                console.error('Subscription error:', error);
                this.showNotification({
                    title: 'Subscription Error',
                    message: error.message,
                    type: 'error'
                });
            }
        });
    }

    getObjectUrl(streamId, objectId) {
        return `${this.serverUrl}/streams/${streamId}/objects/${objectId}`;
    }

    async reloadViewer(streamId, commitData) {
        try {
            console.log('Reloading viewer with new commit:', commitData);
            const newObjectId = commitData.objectId;

            if (!newObjectId) {
                throw new Error('No object ID received with commit');
            }

            const newObjectUrl = this.getObjectUrl(streamId, newObjectId);
            console.log('New object URL:', newObjectUrl);

            // If we have a current object loaded, unload it first
            if (this.currentObjectUrl) {
                await this.viewer.unloadObject(this.currentObjectUrl);
            }

            // Create a new Loader for the object
            const loader = new SpeckleLoader(this.viewer.getWorldTree(), newObjectUrl);
            // Load the new object using the Viewer's loadObject method with the loader
            await this.viewer.loadObject(loader, false);
            console.log('Object loaded successfully');

            // Update current object URL
            this.currentObjectUrl = newObjectUrl;


            console.log('Model reloaded successfully');
            this.showNotification({
                title: 'Model Updated',
                message: commitData.message || 'New version loaded',
                type: 'success'
            });



        } catch (error) {
            console.error('Error reloading viewer:', error);
            this.showNotification({
                title: 'Error',
                message: error.message,
                type: 'error'
            });
        }
    }

    showNotification({ title, message, type = 'info' }) {
        const notification = document.createElement('div');
        notification.innerHTML = `
            <h4>${title}</h4>
            <p>${message}</p>
        `;

        const bgColor = type === 'error' ? '#ffebee' : '#e8f5e9';
        const textColor = type === 'error' ? '#c62828' : '#2e7d32';

        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: ${bgColor};
            color: ${textColor};
            padding: 15px;
            border-radius: 4px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            z-index: 1000;
            animation: slideIn 0.3s ease-out;
        `;

        document.body.appendChild(notification);
        setTimeout(() => {
            notification.style.animation = 'slideOut 0.3s ease-out';
            setTimeout(() => notification.remove(), 300);
        }, 3000);
    }

    stopSubscription() {
        if (this.subscription) {
            this.subscription.unsubscribe();
            this.subscription = null;
        }
    }

    unsubscribeAll() {
        this.stopSubscription();
        if (this.currentObjectUrl) {
            this.viewer.unloadObject(this.currentObjectUrl);
        }
    }
}