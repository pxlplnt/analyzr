define([
    "react",
    "backbone-react-mixin",

    "jsx!views/repository/ListItem",

    "jsx!views/components/Hint"
], function(
    React,
    BackboneMixin,

    ListItem,

    Hint
) {

    return React.createClass({

        displayName: "Repositories",

        mixins: [ BackboneMixin ],

        getInitialState: function() {
            return {
                loading: true
            };
        },

        componentDidMount: function() {
            this.props.collection.once("sync", function() {
                this.setState({
                    loading: false
                });
            }, this);

            this.props.collection.fetch();
        },

        render: function() {
            if(this.state.loading) {
                return (
                    <Hint loading={ true }>
                        Loading repositories...
                    </Hint>
                );
            }

            return (
                <div className="repositories">
                    <table className='table table-hover'>
                        <thead>
                            <tr>
                                <th className='status'>
                                    <abbr title='At least one branch analyzed'>A</abbr>
                                </th>
                                <th className='status'>
                                    <abbr title='At least one branch measured'>M</abbr>
                                </th>
                                <th className='status'>
                                    <abbr title='Anonymous repo access'>S</abbr>
                                </th>
                                <th>Type</th>
                                <th>Location</th>
                                <th></th>
                                <th></th>
                            </tr>
                        </thead>
                        <tbody>
                            { this.props.collection.map(this.renderRepository) }
                        </tbody>
                    </table>
                </div>
            );
        },

        renderRepository: function(repository) {
            return (
                <ListItem
                    key={ repository.cid }
                    model={ repository } />
            );
        }
    });

});
